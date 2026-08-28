from backend.quant.stats import (
    MIN_SAMPLE_SIZE_FOR_CONFIDENCE,
    expectancy,
    max_drawdown,
    profit_factor,
    sample_size_warning,
    win_rate,
)


def test_no_trades_returns_none_not_zero():
    for fn in (win_rate, expectancy, profit_factor, max_drawdown):
        result = fn([])
        assert result.value is None
        assert result.sample_size == 0
        assert result.sample_size_warning is not None


def test_win_rate_basic():
    result = win_rate([10, -5, 20, -3, -1])
    assert result.value == 2 / 5


def test_expectancy_basic():
    result = expectancy([10, -5, 20, -3, -1])
    assert result.value == (10 - 5 + 20 - 3 - 1) / 5


def test_profit_factor_basic():
    result = profit_factor([10, -5, 20, -5])
    assert result.value == 30 / 10


def test_profit_factor_undefined_with_no_losses():
    result = profit_factor([10, 20, 5])
    assert result.value is None
    assert "undefined" in result.sample_size_warning.lower()


def test_max_drawdown_basic():
    # equity: 100 -> 120 (peak) -> 90 (30 drawdown from peak = 25%) -> 130
    result = max_drawdown([100, 120, 90, 130])
    assert abs(result.value - (30 / 120)) < 1e-9


def test_max_drawdown_zero_when_monotonic_increase():
    result = max_drawdown([100, 110, 120, 130])
    assert result.value == 0.0


def test_sample_size_warning_thresholds():
    assert sample_size_warning(0) is not None
    assert sample_size_warning(5) is not None
    assert sample_size_warning(MIN_SAMPLE_SIZE_FOR_CONFIDENCE) is None
    assert sample_size_warning(MIN_SAMPLE_SIZE_FOR_CONFIDENCE - 1) is not None


def test_small_sample_size_flagged_on_every_stat():
    small = [10, -5, 3]
    for fn in (win_rate, expectancy, profit_factor):
        result = fn(small)
        assert result.sample_size_warning is not None
