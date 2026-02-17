from __future__ import annotations

import numpy as np
import pandas as pd


def _check_required_columns(dataframe: pd.DataFrame, required_columns: list[str]) -> None:
    missing_columns = [column_name for column_name in required_columns if column_name not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"缺失必要列: {missing_columns}")


def _parse_trade_date(trade_dates: pd.Series) -> pd.Series:
    parsed_dates = pd.to_datetime(trade_dates.astype("string").str.strip(), errors="coerce")
    invalid_mask = parsed_dates.isna()
    if invalid_mask.any():
        invalid_examples = trade_dates[invalid_mask].head(3).tolist()
        raise ValueError(f"trade_date 无法解析: {invalid_examples}")
    return parsed_dates


def _compute_forward_return(next_price: pd.Series, current_close: pd.Series) -> pd.Series:
    current_close_float = pd.to_numeric(current_close, errors="coerce")
    next_price_float = pd.to_numeric(next_price, errors="coerce")
    valid_mask = current_close_float.notna() & next_price_float.notna() & (current_close_float != 0)
    forward_return = pd.Series(np.nan, index=current_close.index, dtype=float)
    forward_return.loc[valid_mask] = (
        next_price_float.loc[valid_mask] / current_close_float.loc[valid_mask] - 1.0
    )
    return forward_return


def add_next_day_returns(daily_df: pd.DataFrame) -> pd.DataFrame:
    _check_required_columns(daily_df, ["ts_code", "trade_date", "open", "close"])

    output_daily = daily_df.copy()
    output_daily["_original_index"] = output_daily.index
    output_daily["_trade_sort_key"] = _parse_trade_date(output_daily["trade_date"])

    sorted_daily = output_daily.sort_values(["ts_code", "_trade_sort_key", "_original_index"]).copy()
    sorted_daily["_next_open_price"] = sorted_daily.groupby("ts_code")["open"].shift(-1)
    sorted_daily["_next_close_price"] = sorted_daily.groupby("ts_code")["close"].shift(-1)

    sorted_daily["next_open_ret"] = _compute_forward_return(
        sorted_daily["_next_open_price"],
        sorted_daily["close"],
    )
    sorted_daily["next_close_ret"] = _compute_forward_return(
        sorted_daily["_next_close_price"],
        sorted_daily["close"],
    )

    output_with_returns = sorted_daily.sort_values("_original_index").drop(
        columns=["_original_index", "_trade_sort_key", "_next_open_price", "_next_close_price"]
    )
    return output_with_returns

