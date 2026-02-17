from __future__ import annotations

import pandas as pd

from limitup_lab.fill_models import FillModel, can_buy_limitup_day
from limitup_lab.strategy_base import (
    Strategy,
    ensure_columns,
    next_trade_date_series,
    normalize_bool_series,
)


class BuyNonOneWordLimitUpSellNextOpenStrategy(Strategy):
    name = "buy_non_one_word_limitup_sell_next_open"
    exit_price_type = "next_open"

    def __init__(self, fill_model: FillModel = FillModel.CONSERVATIVE) -> None:
        self.fill_model = fill_model

    def generate_entries(self, daily_df: pd.DataFrame) -> pd.Series:
        ensure_columns(daily_df, ["label_limit_up", "label_one_word", "label_sealed"])
        limit_up_flag = normalize_bool_series(daily_df["label_limit_up"])
        non_one_word_flag = ~normalize_bool_series(daily_df["label_one_word"])
        can_buy_flag = daily_df.apply(
            lambda row: can_buy_limitup_day(row.to_dict(), self.fill_model),
            axis=1,
        )
        return (limit_up_flag & non_one_word_flag & can_buy_flag).astype(bool)

    def generate_exits(self, daily_df: pd.DataFrame) -> pd.Series:
        entries = self.generate_entries(daily_df)
        next_dates = next_trade_date_series(daily_df)
        exit_dates = pd.Series(pd.NA, index=daily_df.index, dtype="object")
        exit_dates.loc[entries] = next_dates.loc[entries]
        return exit_dates

