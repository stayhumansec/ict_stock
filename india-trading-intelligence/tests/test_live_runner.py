import csv
import os
import tempfile
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.notifications.base import NotificationChannel, NotificationResult, Severity
from backend.risk.engine import DailyRiskState, RiskConfig, RiskEngine
from backend.signals.signal import SignalState
from backend.smc.config import SMCConfig
from backend.smc.models import Bar
from live.data_sources import read_csv_bars, replay_csv_bars
from live.run_live_manual import ConsoleNotifier, DualNotifier, LiveRunner

KOLKATA = timezone(timedelta(hours=5, minutes=30))


class RecordingNotifier(NotificationChannel):
    def __init__(self):
        self.sent = []

    def is_configured(self) -> bool:
        return True

    def send(self, message: str, severity: Severity) -> NotificationResult:
        self.sent.append((severity, message))
        return NotificationResult(success=True, sent_at=self._now())


def make_bars(values):
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, (o, h, l, c) in enumerate(values):
        bars.append(
            Bar(index=i, timestamp=start + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=1000)
        )
    return bars


# Same verified bullish -> CHoCH -> MSS sequence used in test_structure.py.
_BULLISH_BASE = [
    (100, 101, 99, 100),
    (99, 100, 98, 99),
    (98, 102, 97, 101),
    (101, 101, 96, 97),
    (97, 98, 90, 91),
    (91, 92, 91, 91),
    (92, 95, 92, 94),
    (94, 108, 93, 107),
    (107, 107, 100, 101),
    (101, 102, 100, 101),
    (101, 102, 95, 96),
    (96, 97, 96, 96),
    (96, 97, 96, 96),
]


def make_runner(risk_config=None, starting_equity=0.0):
    notifier = RecordingNotifier()
    risk_engine = RiskEngine(risk_config or RiskConfig())
    risk_state = DailyRiskState(trading_day=date.today(), starting_equity=starting_equity)
    runner = LiveRunner(
        instrument="NIFTY",
        config=SMCConfig(internal_swing_n=2),
        notifier=notifier,
        risk_engine=risk_engine,
        risk_state=risk_state,
    )
    return runner, notifier


def test_choch_creates_developing_signal():
    runner, notifier = make_runner()
    values = _BULLISH_BASE + [(96, 97, 80, 85)]  # bar 13: CHoCH bearish
    for bar in make_bars(values):
        runner.process_bar(bar)

    assert len(runner.signals) == 1
    signal = runner.signals[0]
    assert signal.state == SignalState.DEVELOPING
    severities = [s for s, _ in notifier.sent]
    assert Severity.SETUP in severities


def test_mss_confirms_signal_and_sends_actionable():
    runner, notifier = make_runner()
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),   # bar 13: CHoCH bearish
        (85, 86, 83, 84),   # bar 14
        (84, 85, 40, 45),   # bar 15: MSS confirms
    ]
    for bar in make_bars(values):
        runner.process_bar(bar)

    assert len(runner.signals) == 1
    assert runner.signals[0].state == SignalState.CONFIRMED
    severities = [s for s, _ in notifier.sent]
    assert Severity.ACTIONABLE in severities


def test_choch_failed_invalidates_signal():
    runner, notifier = make_runner()
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),    # bar 13: CHoCH bearish, opposite_extreme = 97
        (85, 105, 84, 102),  # bar 14: reclaims above 97 -> CHOCH_FAILED
    ]
    for bar in make_bars(values):
        runner.process_bar(bar)

    assert len(runner.signals) == 1
    assert runner.signals[0].state == SignalState.INVALIDATED
    severities = [s for s, _ in notifier.sent]
    assert Severity.WARNING in severities


def test_mss_failed_invalidates_confirmed_signal():
    runner, notifier = make_runner()
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),
        (85, 86, 83, 84),
        (84, 85, 40, 45),   # MSS confirms, level = close = 45
        (45, 46, 44, 45),
        (45, 100, 44, 90),  # closes back through 45 -> MSS_FAILED
    ]
    for bar in make_bars(values):
        runner.process_bar(bar)

    assert runner.signals[0].state == SignalState.INVALIDATED


def test_bos_does_not_create_a_signal_or_notify():
    runner, notifier = make_runner()
    values = _BULLISH_BASE + [(96, 116, 95, 115)]  # BOS bullish
    for bar in make_bars(values):
        runner.process_bar(bar)

    assert runner.signals == []
    assert notifier.sent == []


def test_risk_gate_downgrades_actionable_to_warning_when_blocked():
    blocking_config = RiskConfig(max_trades_per_day=1)
    runner, notifier = make_runner(risk_config=blocking_config)
    # Pretend a trade was already taken today, so the gate blocks the next one.
    runner.risk_state.trades_taken_today = 1

    values = _BULLISH_BASE + [
        (96, 97, 80, 85),
        (85, 86, 83, 84),
        (84, 85, 40, 45),  # MSS confirms
    ]
    for bar in make_bars(values):
        runner.process_bar(bar)

    assert runner.signals[0].state == SignalState.CONFIRMED  # structure state still updates
    severities = [s for s, _ in notifier.sent]
    assert Severity.ACTIONABLE not in severities
    assert Severity.WARNING in severities


def test_confirmed_reversal_sweep_sends_info_notification():
    runner, notifier = make_runner()
    # _BULLISH_BASE leaves a swing-high pool at 108 (confirmed at index 9),
    # untouched by any bar through index 12. Add a bar that wicks through
    # it and rejects (a bearish-direction sweep), then a bearish CHoCH -
    # matching direction after the sweep index -> CONFIRMED_REVERSAL.
    values = _BULLISH_BASE + [
        (108, 112, 105, 106),  # sweeps 108, rejects (close 106 < 108)
        (106, 107, 80, 85),    # bearish CHoCH (close 85 < last_low 95)
    ]
    for bar in make_bars(values):
        runner.process_bar(bar)

    infos = [m for s, m in notifier.sent if s == Severity.INFO]
    assert any("swept" in m for m in infos)


def test_csv_round_trip_read_and_replay(tmp_path):
    path = tmp_path / "bars.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-01T09:15:00+05:30", "100", "101", "99", "100.5", "1000"])
        writer.writerow(["2024-01-01T09:20:00+05:30", "100.5", "102", "100", "101.5", "1200"])

    bars = read_csv_bars(str(path))
    assert len(bars) == 2
    assert bars[0].index == 0
    assert bars[1].index == 1
    assert bars[0].close == 100.5

    replayed = list(replay_csv_bars(str(path)))
    assert len(replayed) == 2


def test_csv_missing_columns_raises(tmp_path):
    path = tmp_path / "bad.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "close"])
        writer.writerow(["2024-01-01T09:15:00+05:30", "100", "101"])

    with pytest.raises(ValueError):
        read_csv_bars(str(path))


def test_console_notifier_always_configured(capsys):
    notifier = ConsoleNotifier()
    assert notifier.is_configured() is True
    result = notifier.send("hello", Severity.INFO)
    assert result.success is True
    captured = capsys.readouterr()
    assert "hello" in captured.out


def test_dual_notifier_succeeds_if_any_channel_configured():
    working = RecordingNotifier()

    class BrokenNotifier(NotificationChannel):
        def is_configured(self):
            return False

        def send(self, message, severity):
            raise AssertionError("should never be called when not configured")

    dual = DualNotifier([working, BrokenNotifier()])
    result = dual.send("hi", Severity.INFO)
    assert result.success is True
    assert working.sent == [(Severity.INFO, "hi")]
