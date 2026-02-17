from __future__ import annotations

from pathlib import Path

import pandas as pd

from limitup_lab.strategies import (
    BuyFirstLimitUpSellNextCloseStrategy,
    BuyNonOneWordLimitUpSellNextOpenStrategy,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def test_buy_first_limitup_sell_next_close_has_non_empty_signals() -> None:
    labeled_daily = pd.read_csv(FIXTURE_DIR / "strategy_signals.csv")
    strategy = BuyFirstLimitUpSellNextCloseStrategy()

    entries = strategy.generate_entries(labeled_daily)
    exits = strategy.generate_exits(labeled_daily)

    assert entries.any()
    assert strategy.name == "buy_first_limitup_sell_next_close"
    assert strategy.exit_price_type == "next_close"
    assert exits.loc[entries].notna().all()


def test_buy_non_one_word_limitup_sell_next_open_has_non_empty_signals() -> None:
    labeled_daily = pd.read_csv(FIXTURE_DIR / "strategy_signals.csv")
    strategy = BuyNonOneWordLimitUpSellNextOpenStrategy()

    entries = strategy.generate_entries(labeled_daily)
    exits = strategy.generate_exits(labeled_daily)

    assert entries.any()
    assert strategy.name == "buy_non_one_word_limitup_sell_next_open"
    assert strategy.exit_price_type == "next_open"
    assert exits.loc[entries].notna().all()

