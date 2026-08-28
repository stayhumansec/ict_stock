from datetime import date

import pytest

from backend.risk.engine import DailyRiskState, RiskConfig, RiskEngine


def make_engine(**overrides) -> RiskEngine:
    defaults = dict(risk_per_trade_pct=1.0, max_daily_loss_pct=2.0, max_trades_per_day=5, max_open_positions=1)
    defaults.update(overrides)
    return RiskEngine(RiskConfig(**defaults))


def test_position_size_basic_fixed_percent_risk():
    engine = make_engine(risk_per_trade_pct=1.0)
    # equity 100,000, risk 1% = 1000. entry-stop distance = 50. qty = 20.
    result = engine.position_size(account_equity=100_000, entry_price=22000, stop_loss_price=21950, lot_size=1)
    assert result.quantity == 20
    assert result.risk_amount == 1000
    assert result.risk_per_unit == 50


def test_position_size_rounds_down_to_whole_lots():
    engine = make_engine(risk_per_trade_pct=1.0)
    # risk_amount=1000, risk_per_unit=50 -> raw qty 20, lot_size=25 -> 0 lots
    result = engine.position_size(account_equity=100_000, entry_price=22000, stop_loss_price=21950, lot_size=25)
    assert result.quantity == 0
    assert result.capped is True


def test_position_size_zero_on_invalid_stop_distance():
    engine = make_engine()
    result = engine.position_size(account_equity=100_000, entry_price=22000, stop_loss_price=22000, lot_size=1)
    assert result.quantity == 0
    assert "invalid" in result.note.lower()


def test_position_size_zero_on_non_positive_equity():
    engine = make_engine()
    result = engine.position_size(account_equity=0, entry_price=22000, stop_loss_price=21950, lot_size=1)
    assert result.quantity == 0


def test_daily_gate_allows_when_within_limits():
    engine = make_engine(max_daily_loss_pct=2.0, max_trades_per_day=5, max_open_positions=1)
    state = DailyRiskState(trading_day=date(2024, 1, 1), starting_equity=100_000, realized_pnl_today=-500, trades_taken_today=1, open_positions=0)
    decision = engine.check_daily_gate(state)
    assert decision.allowed is True
    assert decision.reasons == []


def test_daily_gate_blocks_on_max_daily_loss():
    engine = make_engine(max_daily_loss_pct=2.0)
    state = DailyRiskState(trading_day=date(2024, 1, 1), starting_equity=100_000, realized_pnl_today=-2500, trades_taken_today=1, open_positions=0)
    decision = engine.check_daily_gate(state)
    assert decision.allowed is False
    assert any("Daily loss limit" in r for r in decision.reasons)


def test_daily_gate_blocks_on_max_trades_per_day():
    engine = make_engine(max_trades_per_day=3)
    state = DailyRiskState(trading_day=date(2024, 1, 1), starting_equity=100_000, realized_pnl_today=0, trades_taken_today=3, open_positions=0)
    decision = engine.check_daily_gate(state)
    assert decision.allowed is False
    assert any("Max trades per day" in r for r in decision.reasons)


def test_daily_gate_blocks_on_max_open_positions():
    engine = make_engine(max_open_positions=1)
    state = DailyRiskState(trading_day=date(2024, 1, 1), starting_equity=100_000, realized_pnl_today=0, trades_taken_today=0, open_positions=1)
    decision = engine.check_daily_gate(state)
    assert decision.allowed is False
    assert any("Max open positions" in r for r in decision.reasons)


def test_daily_gate_can_stack_multiple_reasons():
    engine = make_engine(max_daily_loss_pct=2.0, max_trades_per_day=1)
    state = DailyRiskState(trading_day=date(2024, 1, 1), starting_equity=100_000, realized_pnl_today=-3000, trades_taken_today=2, open_positions=0)
    decision = engine.check_daily_gate(state)
    assert decision.allowed is False
    assert len(decision.reasons) == 2


def test_check_daily_gate_does_not_mutate_state():
    engine = make_engine()
    state = DailyRiskState(trading_day=date(2024, 1, 1), starting_equity=100_000, realized_pnl_today=-100, trades_taken_today=1, open_positions=0)
    before = (state.realized_pnl_today, state.trades_taken_today, state.open_positions)
    engine.check_daily_gate(state)
    after = (state.realized_pnl_today, state.trades_taken_today, state.open_positions)
    assert before == after


def test_invalid_config_raises():
    with pytest.raises(ValueError):
        RiskConfig(risk_per_trade_pct=0)
    with pytest.raises(ValueError):
        RiskConfig(max_trades_per_day=0)
