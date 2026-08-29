"""Wires market data -> SMCEngine -> Signal -> Telegram together into one
continuously-running (or CSV-replayed) manual-execution pipeline.

NO ORDER PLACEMENT ANYWHERE IN THIS FILE. Automation stays off by
default - this script only ever reads market data and sends
notifications. The trader decides and executes manually, outside this
system entirely.

Usage:
    # Safe, no broker/network needed - replays a CSV of bars:
    python -m live.run_live_manual --csv path/to/bars.csv --instrument NIFTY

    # Live, against a real Angel One connection (requires ANGEL_ONE_* env
    # vars and an already-known symbol token for the instrument):
    python -m live.run_live_manual --live --instrument NIFTY \\
        --exchange NSE --symbol-token <token> --interval FIVE_MINUTE
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Iterator, Optional, Set

from backend.brokers.angel_one import AngelOneAuthError, AngelOneBroker
from backend.database import db as database
from backend.database.models import NotificationRecord, SignalRecord
from backend.notifications.base import NotificationChannel, NotificationResult, Severity
from backend.notifications.telegram import TelegramNotifier
from backend.risk.engine import DailyRiskState, RiskConfig, RiskEngine
from backend.signals.mode import MethodologyMode
from backend.signals.reasoning import ConfluenceSummary, build_confluence_summary, refs_to_json
from backend.signals.signal import Signal, SignalState
from backend.smc.config import SMCConfig
from backend.smc.engine import SMCEngine
from backend.smc.models import Bar, Direction, EngineResult, StructureEventType

from .data_sources import poll_angel_one_bars, replay_csv_bars


class ConsoleNotifier(NotificationChannel):
    """Always "configured" - prints to stdout. Used as a fallback so the
    pipeline is observable even without Telegram set up, and alongside
    Telegram so the person watching the terminal sees the same alerts."""

    def is_configured(self) -> bool:
        return True

    def send(self, message: str, severity: Severity) -> NotificationResult:
        print(f"[{severity.value}] {message}")
        return NotificationResult(success=True, sent_at=self._now())


class DualNotifier(NotificationChannel):
    """Sends to every configured channel; never fails the caller just
    because one channel isn't configured."""

    def __init__(self, channels: list):
        self.channels = channels

    def is_configured(self) -> bool:
        return any(c.is_configured() for c in self.channels)

    def send(self, message: str, severity: Severity) -> NotificationResult:
        results = [c.send(message, severity) for c in self.channels if c.is_configured()]
        success = any(r.success for r in results)
        error = "; ".join(r.error for r in results if not r.success)
        return NotificationResult(success=success, sent_at=self._now(), error=error)


def _direction_word(direction: Direction) -> str:
    return "bullish" if direction == Direction.BULLISH else "bearish"


@dataclass
class LiveRunner:
    instrument: str
    config: SMCConfig
    notifier: NotificationChannel
    risk_engine: RiskEngine
    risk_state: DailyRiskState
    db_conn: Optional[sqlite3.Connection] = None
    data_source: str = "csv"  # "angel_one" or "csv" - drives ConfluenceSummary.data_quality

    bars: list = field(default_factory=list)
    seen_structure_event_ids: Set[int] = field(default_factory=set)
    seen_sweep_ids: Set[int] = field(default_factory=set)
    signal_by_event_id: Dict[int, Signal] = field(default_factory=dict)
    signals: list = field(default_factory=list)
    _next_signal_id: int = 0

    def _build_summary(self, signal: Signal, result: EngineResult, risk_gate_allowed: bool) -> ConfluenceSummary:
        return build_confluence_summary(
            result,
            event_ids=signal.structure_event_ids,
            direction=signal.direction,
            state_is_confirmed=(signal.state == SignalState.CONFIRMED),
            risk_gate_allowed=risk_gate_allowed,
            data_source=self.data_source,
        )

    def _persist_new_signal(self, signal: Signal, summary: ConfluenceSummary) -> None:
        if self.db_conn is None:
            return
        record = SignalRecord(
            id=None,
            instrument=signal.instrument,
            mode=signal.mode.value,
            direction=signal.direction.value,
            state=signal.state.value,
            created_index=signal.created_index,
            created_at=signal.created_at,
            updated_at=signal.created_at,
            targets_json=database.targets_to_json(signal.targets),
            structure_event_ids_json=database.event_ids_to_json(signal.structure_event_ids),
            score=summary.score,
            grade=summary.grade,
            data_quality=summary.data_quality,
            decision=summary.decision,
            reasoning_chain_json=json.dumps(summary.reasoning_chain),
            core_signal_json=refs_to_json(summary.core_signal),
            confirmations_json=refs_to_json(summary.confirmations),
            conflicts_json=refs_to_json(summary.conflicts),
        )
        signal.record_id = database.insert_signal(self.db_conn, record)

    def _persist_signal_update(self, signal: Signal, summary: ConfluenceSummary) -> None:
        if self.db_conn is None or signal.record_id is None:
            return
        database.update_signal_state(
            self.db_conn,
            signal.record_id,
            signal.state.value,
            datetime.now(),
            structure_event_ids_json=database.event_ids_to_json(signal.structure_event_ids),
            score=summary.score,
            grade=summary.grade,
            data_quality=summary.data_quality,
            decision=summary.decision,
            reasoning_chain_json=json.dumps(summary.reasoning_chain),
            core_signal_json=refs_to_json(summary.core_signal),
            confirmations_json=refs_to_json(summary.confirmations),
            conflicts_json=refs_to_json(summary.conflicts),
        )

    def _notify(self, message: str, severity: Severity, signal: Optional[Signal] = None) -> None:
        result = self.notifier.send(message, severity)
        if self.db_conn is None:
            return
        record = NotificationRecord(
            id=None,
            signal_id=signal.record_id if signal else None,
            channel="app",
            severity=severity.value,
            message=message,
            success=result.success,
            sent_at=result.sent_at,
            error=result.error,
        )
        database.insert_notification(self.db_conn, record)

    def process_bar(self, bar: Bar) -> None:
        self.bars.append(bar)
        result = SMCEngine(self.config).run(self.bars)

        if self.db_conn is not None:
            database.upsert_heartbeat(self.db_conn, self.instrument, bar.timestamp, bar.close, self.data_source)

        new_events = [e for e in result.structure_events if e.event_id not in self.seen_structure_event_ids]
        for event in sorted(new_events, key=lambda e: e.confirmed_index):
            self.seen_structure_event_ids.add(event.event_id)
            self._handle_structure_event(event, bar, result)

        new_sweeps = [s for s in result.liquidity_sweeps if s.sweep_id not in self.seen_sweep_ids]
        for sweep in new_sweeps:
            self.seen_sweep_ids.add(sweep.sweep_id)
            if sweep.follow_through.value == "CONFIRMED_REVERSAL":
                self._notify(
                    f"{self.instrument}: {sweep.pool_type.value} liquidity swept with rejection "
                    f"(price {sweep.swept_price:.2f}) - potential {_direction_word(sweep.direction)} reversal context.",
                    Severity.INFO,
                )

    def _handle_structure_event(self, event, bar: Bar, result: EngineResult) -> None:
        if event.event_type == StructureEventType.CHOCH:
            signal = Signal(
                signal_id=self._next_signal_id,
                instrument=self.instrument,
                mode=MethodologyMode.SMC,
                direction=event.direction,
                created_index=bar.index,
                created_at=bar.timestamp,
                structure_event_ids=[event.event_id],
            )
            self._next_signal_id += 1
            self.signal_by_event_id[event.event_id] = signal
            self.signals.append(signal)
            summary = self._build_summary(signal, result, risk_gate_allowed=True)
            self._persist_new_signal(signal, summary)
            self._notify(
                f"{self.instrument}: {_direction_word(event.direction)} CHoCH at {event.reference_price:.2f} "
                f"- developing reversal candidate.",
                Severity.SETUP,
                signal=signal,
            )

        elif event.event_type == StructureEventType.MSS:
            signal = self.signal_by_event_id.get(event.related_event_id)
            if signal is None or signal.is_terminal():
                return
            signal.transition(SignalState.CONFIRMED, at_index=bar.index, reason="MSS confirmed")
            signal.structure_event_ids.append(event.event_id)
            self.signal_by_event_id[event.event_id] = signal

            decision = self.risk_engine.check_daily_gate(self.risk_state)
            summary = self._build_summary(signal, result, risk_gate_allowed=decision.allowed)
            self._persist_signal_update(signal, summary)

            if decision.allowed:
                self._notify(
                    f"{self.instrument}: {_direction_word(event.direction)} MSS confirmed at "
                    f"{event.reference_price:.2f}. Structure setup confirmed - entry/stop/target sizing is not "
                    f"computed by this release; review manually. REVIEW / MANUAL ENTRY.",
                    Severity.ACTIONABLE,
                    signal=signal,
                )
            else:
                self._notify(
                    f"{self.instrument}: {_direction_word(event.direction)} MSS confirmed at "
                    f"{event.reference_price:.2f}, but the daily risk gate is blocking new entries today "
                    f"({'; '.join(decision.reasons)}). For awareness only - no action suggested.",
                    Severity.WARNING,
                    signal=signal,
                )

        elif event.event_type == StructureEventType.CHOCH_FAILED:
            signal = self.signal_by_event_id.get(event.related_event_id)
            if signal is None or signal.is_terminal():
                return
            signal.transition(SignalState.INVALIDATED, at_index=bar.index, reason="CHoCH failed")
            signal.structure_event_ids.append(event.event_id)
            summary = self._build_summary(signal, result, risk_gate_allowed=False)
            self._persist_signal_update(signal, summary)
            self._notify(
                f"{self.instrument}: CHoCH at {event.reference_price:.2f} failed - setup invalidated.",
                Severity.WARNING,
                signal=signal,
            )

        elif event.event_type == StructureEventType.MSS_FAILED:
            signal = self.signal_by_event_id.get(event.related_event_id)
            if signal is None or signal.is_terminal():
                return
            signal.transition(SignalState.INVALIDATED, at_index=bar.index, reason="MSS failed")
            signal.structure_event_ids.append(event.event_id)
            summary = self._build_summary(signal, result, risk_gate_allowed=False)
            self._persist_signal_update(signal, summary)
            self._notify(
                f"{self.instrument}: MSS at {event.reference_price:.2f} failed - price closed back through "
                f"the confirmation level. Setup invalidated.",
                Severity.WARNING,
                signal=signal,
            )

        # BOS is intentionally not notified here - it's continuation
        # confirmation of already-known structure, not a new setup, and
        # alerting on every BOS would violate "not tuned to maximize
        # signal count."


def build_notifier() -> NotificationChannel:
    telegram = TelegramNotifier()
    console = ConsoleNotifier()
    if not telegram.is_configured():
        print("[startup] Telegram is not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID) - "
              "alerts will print to the console only.")
    return DualNotifier([telegram, console])


def build_bar_source(args: argparse.Namespace) -> Iterator[Bar]:
    if args.csv:
        return replay_csv_bars(args.csv, delay_seconds=args.delay_seconds)

    broker = AngelOneBroker()
    broker.authenticate()
    print("[startup] Authenticated with Angel One.")
    return poll_angel_one_bars(
        broker,
        exchange=args.exchange,
        symbol_token=args.symbol_token,
        interval=args.interval,
        poll_seconds=args.poll_seconds,
        lookback_minutes=args.lookback_minutes,
    )


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instrument", default="NIFTY", choices=["NIFTY", "BANKNIFTY"])

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", help="Path to a CSV of bars to replay (timestamp,open,high,low,close,volume).")
    source.add_argument("--live", action="store_true", help="Connect to Angel One for live data.")

    parser.add_argument("--delay-seconds", type=float, default=0.0, help="CSV replay: pause between bars.")

    parser.add_argument("--exchange", default="NSE", help="Live mode: exchange segment.")
    parser.add_argument("--symbol-token", help="Live mode: Angel One numeric symbol token for the instrument.")
    parser.add_argument("--interval", default="FIVE_MINUTE", help="Live mode: candle interval.")
    parser.add_argument("--poll-seconds", type=float, default=60.0, help="Live mode: seconds between polls.")
    parser.add_argument("--lookback-minutes", type=int, default=60, help="Live mode: historical window per poll.")

    parser.add_argument("--account-equity", type=float, default=0.0, help="For the risk gate display only.")
    parser.add_argument("--risk-per-trade-pct", type=float, default=0.5)
    parser.add_argument("--max-daily-loss-pct", type=float, default=2.0)
    parser.add_argument("--max-trades-per-day", type=int, default=5)

    parser.add_argument(
        "--db",
        default=None,
        help="Path to a SQLite file to persist signals/notifications to (e.g. smc.db). "
        "Omit to run without persistence, same as before this flag existed.",
    )

    args = parser.parse_args(argv)
    if args.live and not args.symbol_token:
        parser.error("--live requires --symbol-token")
    return args


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)

    notifier = build_notifier()
    risk_config = RiskConfig(
        risk_per_trade_pct=args.risk_per_trade_pct,
        max_daily_loss_pct=args.max_daily_loss_pct,
        max_trades_per_day=args.max_trades_per_day,
    )
    risk_engine = RiskEngine(risk_config)
    # Signals and notifications are now persisted when --db is given (see
    # LiveRunner._persist_new_signal / _persist_signal_update), but
    # realized_pnl_today and trades_taken_today still can't be honestly
    # tracked here - Release 1 has no fill/execution feedback from manual
    # trades, so they stay at zero for the life of the process. The risk
    # gate is wired in for real but will only ever trigger on
    # max_trades/max_positions if you update this state manually; it
    # never fabricates a loss that didn't happen.
    risk_state = DailyRiskState(trading_day=date.today(), starting_equity=args.account_equity)

    db_conn = database.connect(args.db) if args.db else None
    if db_conn:
        print(f"[startup] Persisting signals/notifications to {args.db}")

    runner = LiveRunner(
        instrument=args.instrument,
        config=SMCConfig(),
        notifier=notifier,
        risk_engine=risk_engine,
        risk_state=risk_state,
        db_conn=db_conn,
        data_source="angel_one" if args.live else "csv",
    )

    try:
        source = build_bar_source(args)
    except AngelOneAuthError as exc:
        print(f"Angel One authentication failed: {exc}")
        return 1

    bar_count = 0
    try:
        for bar in source:
            runner.process_bar(bar)
            bar_count += 1
    except KeyboardInterrupt:
        print("\n[shutdown] Interrupted by user.")
    finally:
        if db_conn:
            db_conn.close()

    print(f"\n[summary] Processed {bar_count} bars, created {len(runner.signals)} signal(s).")
    for s in runner.signals:
        print(f"  signal {s.signal_id}: {s.instrument} {s.direction.value} state={s.state.value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
