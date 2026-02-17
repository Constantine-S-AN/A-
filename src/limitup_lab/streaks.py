from __future__ import annotations

from pathlib import Path

import pandas as pd

from limitup_lab.limits import is_price_limit_applicable


def _check_required_columns(dataframe: pd.DataFrame, required_columns: list[str]) -> None:
    missing_columns = [column_name for column_name in required_columns if column_name not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"缺失必要列: {missing_columns}")


def _normalize_trade_date_series(trade_dates: pd.Series) -> pd.Series:
    parsed_dates = pd.to_datetime(trade_dates.astype("string").str.strip(), errors="coerce")
    invalid_mask = parsed_dates.isna()
    if invalid_mask.any():
        invalid_examples = trade_dates[invalid_mask].head(3).tolist()
        raise ValueError(f"trade_date 无法解析: {invalid_examples}")
    return parsed_dates.dt.strftime("%Y%m%d")


def _coerce_bool_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    normalized = values.astype("string").str.strip().str.lower()
    true_values = {"1", "true", "t", "yes", "y"}
    return normalized.isin(true_values)


def _instrument_lookup(instruments_df: pd.DataFrame) -> dict[str, dict[str, object]]:
    _check_required_columns(instruments_df, ["ts_code"])
    normalized = instruments_df.copy()
    normalized["ts_code"] = normalized["ts_code"].astype("string").str.strip()
    for column_name, default_value in [("board", "UNKNOWN"), ("is_st", False), ("list_date", None)]:
        if column_name not in normalized.columns:
            normalized[column_name] = default_value

    records = normalized.drop_duplicates(subset=["ts_code"], keep="last").to_dict(orient="records")
    lookup: dict[str, dict[str, object]] = {}
    for row in records:
        stock_code = str(row["ts_code"]).strip()
        lookup[stock_code] = {
            "board": row.get("board", "UNKNOWN"),
            "is_st": row.get("is_st", False),
            "list_date": row.get("list_date"),
        }
    return lookup


def compute_limitup_streak(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute consecutive limit-up streak count by ts_code and trade_date.

    Gap handling:
    - If a symbol misses any market trade date present in the input dataset,
      streak resets on the next observed row for that symbol.
    """

    _check_required_columns(daily_df, ["ts_code", "trade_date", "label_limit_up"])

    labeled_daily = daily_df.copy()
    labeled_daily["trade_date"] = _normalize_trade_date_series(labeled_daily["trade_date"])
    labeled_daily["label_limit_up"] = _coerce_bool_series(labeled_daily["label_limit_up"])

    market_trade_dates = sorted(labeled_daily["trade_date"].unique().tolist())
    market_trade_positions = {trade_date: position for position, trade_date in enumerate(market_trade_dates)}

    sorted_daily = labeled_daily.sort_values(["ts_code", "trade_date"]).copy()
    sorted_daily["streak_up"] = 0

    for stock_code, stock_daily in sorted_daily.groupby("ts_code", sort=False):
        previous_streak = 0
        previous_is_limit_up = False
        previous_trade_position: int | None = None

        for row_index, row in stock_daily.iterrows():
            current_is_limit_up = bool(row["label_limit_up"])
            current_trade_position = market_trade_positions[row["trade_date"]]
            is_continuous = (
                previous_trade_position is not None and current_trade_position - previous_trade_position == 1
            )

            if current_is_limit_up:
                current_streak = previous_streak + 1 if (previous_is_limit_up and is_continuous) else 1
            else:
                current_streak = 0

            sorted_daily.at[row_index, "streak_up"] = current_streak
            previous_streak = current_streak
            previous_is_limit_up = current_is_limit_up
            previous_trade_position = current_trade_position

    return sorted_daily.sort_index()


def exclude_unlimited_days(
    daily_df: pd.DataFrame,
    instruments_df: pd.DataFrame | None = None,
    rules_path: str | Path | None = None,
) -> pd.DataFrame:
    _check_required_columns(daily_df, ["ts_code", "trade_date"])
    filtered_daily = daily_df.copy()
    filtered_daily["trade_date"] = _normalize_trade_date_series(filtered_daily["trade_date"])

    if "price_limit_applicable" in filtered_daily.columns:
        applicable_mask = _coerce_bool_series(filtered_daily["price_limit_applicable"])
        return filtered_daily.loc[applicable_mask].reset_index(drop=True)

    if instruments_df is None:
        raise ValueError("instruments_df 不能为空：缺少 price_limit_applicable 列时需要它来判断")

    lookup = _instrument_lookup(instruments_df)
    applicable_mask = filtered_daily.apply(
        lambda row: is_price_limit_applicable(
            lookup.get(
                str(row["ts_code"]).strip(),
                {"board": "UNKNOWN", "is_st": False, "list_date": None},
            ),
            str(row["trade_date"]),
            rules_path=rules_path,
        ),
        axis=1,
    )
    return filtered_daily.loc[applicable_mask].reset_index(drop=True)


def exclude_suspended(daily_df: pd.DataFrame) -> pd.DataFrame:
    _check_required_columns(daily_df, ["vol"])
    filtered_daily = daily_df.copy()
    traded_volume = pd.to_numeric(filtered_daily["vol"], errors="coerce").fillna(0.0)
    return filtered_daily.loc[traded_volume > 0].reset_index(drop=True)

