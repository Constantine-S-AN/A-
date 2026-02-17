from __future__ import annotations

import pandas as pd

from limitup_lab.fill_models import FillModel, can_buy_limitup_day
from limitup_lab.strategy_base import (
    Strategy,
    ensure_columns,
    next_trade_date_series,
    normalize_bool_series,
)


class BuyFirstLimitUpSellNextCloseStrategy(Strategy):
    name = "buy_first_limitup_sell_next_close"
    exit_price_type = "next_close"

    def __init__(self, fill_model: FillModel = FillModel.CONSERVATIVE) -> None:
        self.fill_model = fill_model

    def generate_entries(self, daily_df: pd.DataFrame) -> pd.Series:
        ensure_columns(daily_df, ["label_limit_up", "streak_up", "label_sealed", "label_one_word"])
        limit_up_flag = normalize_bool_series(daily_df["label_limit_up"])
        first_board_flag = pd.to_numeric(daily_df["streak_up"], errors="coerce").fillna(0).eq(1)
        can_buy_flag = daily_df.apply(
            lambda row: can_buy_limitup_day(row.to_dict(), self.fill_model),
            axis=1,
        )
        return (limit_up_flag & first_board_flag & can_buy_flag).astype(bool)

    def generate_exits(self, daily_df: pd.DataFrame) -> pd.Series:
        entries = self.generate_entries(daily_df)
        next_dates = next_trade_date_series(daily_df)
        exit_dates = pd.Series(pd.NA, index=daily_df.index, dtype="object")
        exit_dates.loc[entries] = next_dates.loc[entries]
        return exit_dates

