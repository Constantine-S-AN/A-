from __future__ import annotations

import pandas as pd

from limitup_lab.backtest import run_backtest
from limitup_lab.fill_models import FillModel
from limitup_lab.strategies import (
    BuyFirstLimitUpSellNextCloseStrategy,
)


def test_backtest_cost_model_reduces_net_return() -> None:
    daily_bars = pd.DataFrame(
        [
            {
                "ts_code": "AAA",
                "trade_date": "20240102",
                "open": 10.80,
                "close": 11.00,
                "label_limit_up": True,
                "streak_up": 1,
                "label_one_word": False,
                "label_sealed": False,
            },
            {
                "ts_code": "AAA",
                "trade_date": "20240103",
                "open": 11.20,
                "close": 11.50,
                "label_limit_up": False,
                "streak_up": 0,
                "label_one_word": False,
                "label_sealed": False,
            },
        ]
    )
    strategy = BuyFirstLimitUpSellNextCloseStrategy()

    result_no_cost = run_backtest(
        daily_bars,
        strategy=strategy,
        fill_model=FillModel.CONSERVATIVE,
        fee_bps=0.0,
        slippage_bps=0.0,
    )
    result_with_cost = run_backtest(
        daily_bars,
        strategy=strategy,
        fill_model=FillModel.CONSERVATIVE,
        fee_bps=10.0,
        slippage_bps=10.0,
    )

    assert len(result_no_cost.trades) == 1
    assert len(result_with_cost.trades) == 1
    assert result_with_cost.trades.loc[0, "ret_net"] < result_no_cost.trades.loc[0, "ret_net"]
    assert result_with_cost.equity_curve["equity"].iloc[-1] < result_no_cost.equity_curve["equity"].iloc[-1]


def test_same_strategy_differs_between_ideal_and_conservative_fill() -> None:
    daily_bars = pd.DataFrame(
        [
            {
                "ts_code": "AAA",
                "trade_date": "20240102",
                "open": 10.90,
                "close": 11.00,
                "label_limit_up": True,
                "streak_up": 1,
                "label_one_word": True,
                "label_sealed": True,
            },
            {
                "ts_code": "AAA",
                "trade_date": "20240103",
                "open": 11.20,
                "close": 11.40,
                "label_limit_up": False,
                "streak_up": 0,
                "label_one_word": False,
                "label_sealed": False,
            },
        ]
    )
    strategy = BuyFirstLimitUpSellNextCloseStrategy()

    ideal_result = run_backtest(
        daily_bars,
        strategy=strategy,
        fill_model=FillModel.IDEAL,
        fee_bps=0.0,
        slippage_bps=0.0,
    )
    conservative_result = run_backtest(
        daily_bars,
        strategy=strategy,
        fill_model=FillModel.CONSERVATIVE,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    assert len(ideal_result.trades) == 1
    assert len(conservative_result.trades) == 0
    assert ideal_result.equity_curve["equity"].iloc[-1] > conservative_result.equity_curve["equity"].iloc[-1]
