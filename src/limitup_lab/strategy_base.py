from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


def ensure_columns(dataframe: pd.DataFrame, required_columns: list[str]) -> None:
    missing_columns = [column_name for column_name in required_columns if column_name not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"缺失必要列: {missing_columns}")


def parse_trade_dates(trade_dates: pd.Series) -> pd.Series:
    parsed_dates = pd.to_datetime(trade_dates.astype("string").str.strip(), errors="coerce")
    invalid_mask = parsed_dates.isna()
    if invalid_mask.any():
        invalid_examples = trade_dates[invalid_mask].head(3).tolist()
        raise ValueError(f"trade_date 无法解析: {invalid_examples}")
    return parsed_dates


def normalize_bool_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    normalized_text = values.astype("string").str.strip().str.lower()
    true_values = {"1", "true", "t", "yes", "y"}
    return normalized_text.isin(true_values)


def next_trade_date_series(daily_df: pd.DataFrame) -> pd.Series:
    ensure_columns(daily_df, ["ts_code", "trade_date"])

    ordered_daily = daily_df.copy()
    ordered_daily["_original_order"] = ordered_daily.index
    ordered_daily["_trade_sort_key"] = parse_trade_dates(ordered_daily["trade_date"])
    ordered_daily = ordered_daily.sort_values(["ts_code", "_trade_sort_key", "_original_order"])
    ordered_daily["_next_trade_date"] = ordered_daily.groupby("ts_code")["trade_date"].shift(-1)

    restored_next_date = ordered_daily.sort_values("_original_order")["_next_trade_date"]
    return restored_next_date


class Strategy(ABC):
    name: str
    exit_price_type: str

    @abstractmethod
    def generate_entries(self, daily_df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError

    @abstractmethod
    def generate_exits(self, daily_df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError

