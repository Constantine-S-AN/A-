from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from limitup_lab.limits import compute_limit_price, is_price_limit_applicable, pick_limit_params


DEFAULT_EPS = 1e-6


def _build_instrument_lookup(instruments_df: pd.DataFrame) -> dict[str, dict[str, object]]:
    if "ts_code" not in instruments_df.columns:
        raise ValueError("instruments_df 缺少必要列: ['ts_code']")

    normalized_instruments = instruments_df.copy()
    for column_name, default_value in [("board", "UNKNOWN"), ("is_st", False), ("list_date", None)]:
        if column_name not in normalized_instruments.columns:
            normalized_instruments[column_name] = default_value
    normalized_instruments["ts_code"] = normalized_instruments["ts_code"].astype("string").str.strip()
    normalized_instruments = normalized_instruments.drop_duplicates(subset=["ts_code"], keep="last")

    lookup: dict[str, dict[str, object]] = {}
    for row in normalized_instruments.to_dict(orient="records"):
        ts_code = str(row.get("ts_code", "")).strip()
        if not ts_code:
            continue
        lookup[ts_code] = {
            "board": row.get("board", "UNKNOWN"),
            "is_st": row.get("is_st", False),
            "list_date": row.get("list_date"),
        }
    return lookup


def _get_instrument_row(
    instrument_lookup: dict[str, dict[str, object]],
    ts_code: object,
) -> dict[str, object]:
    normalized_ts_code = str(ts_code).strip()
    return instrument_lookup.get(
        normalized_ts_code,
        {"board": "UNKNOWN", "is_st": False, "list_date": None},
    )


def _check_daily_columns(daily_df: pd.DataFrame, required_columns: list[str]) -> None:
    missing_columns = [column_name for column_name in required_columns if column_name not in daily_df.columns]
    if missing_columns:
        raise ValueError(f"daily_df 缺少必要列: {missing_columns}")


def _is_close_to_limit(
    value_series: pd.Series,
    limit_price_series: pd.Series,
    eps: float,
) -> pd.Series:
    return pd.Series(
        np.isclose(
            pd.to_numeric(value_series, errors="coerce"),
            pd.to_numeric(limit_price_series, errors="coerce"),
            atol=eps,
            rtol=0.0,
        ),
        index=value_series.index,
    )


def add_limit_prices(
    daily_df: pd.DataFrame,
    instruments_df: pd.DataFrame,
    rules_path: str | Path | None = None,
) -> pd.DataFrame:
    _check_daily_columns(daily_df, ["ts_code", "pre_close"])
    instrument_lookup = _build_instrument_lookup(instruments_df)

    output_daily = daily_df.copy()

    def calculate_limit_price(row: pd.Series) -> float:
        instrument_row = _get_instrument_row(instrument_lookup, row["ts_code"])
        up_limit, _, _ = pick_limit_params(instrument_row, rules_path=rules_path)
        return float(compute_limit_price(row["pre_close"], up_limit))

    output_daily["limit_up_price"] = output_daily.apply(calculate_limit_price, axis=1)
    return output_daily


def label_limit_up(
    daily_df: pd.DataFrame,
    instruments_df: pd.DataFrame,
    eps: float = DEFAULT_EPS,
    rules_path: str | Path | None = None,
) -> pd.DataFrame:
    _check_daily_columns(daily_df, ["ts_code", "trade_date", "high", "close", "pre_close"])
    output_daily = add_limit_prices(daily_df, instruments_df, rules_path=rules_path)
    instrument_lookup = _build_instrument_lookup(instruments_df)

    output_daily["price_limit_applicable"] = output_daily.apply(
        lambda row: is_price_limit_applicable(
            _get_instrument_row(instrument_lookup, row["ts_code"]),
            str(row["trade_date"]),
            rules_path=rules_path,
        ),
        axis=1,
    )
    close_hits_limit = _is_close_to_limit(output_daily["close"], output_daily["limit_up_price"], eps=eps)
    high_hits_limit = _is_close_to_limit(output_daily["high"], output_daily["limit_up_price"], eps=eps)
    output_daily["label_limit_up"] = (
        output_daily["price_limit_applicable"] & close_hits_limit & high_hits_limit
    ).astype(bool)
    return output_daily


def label_one_word(
    daily_df: pd.DataFrame,
    instruments_df: pd.DataFrame,
    eps: float = DEFAULT_EPS,
    rules_path: str | Path | None = None,
) -> pd.DataFrame:
    _check_daily_columns(daily_df, ["open", "high", "low", "close", "trade_date", "ts_code", "pre_close"])
    output_daily = label_limit_up(daily_df, instruments_df, eps=eps, rules_path=rules_path)
    open_hits_limit = _is_close_to_limit(output_daily["open"], output_daily["limit_up_price"], eps=eps)
    high_hits_limit = _is_close_to_limit(output_daily["high"], output_daily["limit_up_price"], eps=eps)
    low_hits_limit = _is_close_to_limit(output_daily["low"], output_daily["limit_up_price"], eps=eps)
    close_hits_limit = _is_close_to_limit(output_daily["close"], output_daily["limit_up_price"], eps=eps)
    output_daily["label_one_word"] = (
        output_daily["label_limit_up"]
        & open_hits_limit
        & high_hits_limit
        & low_hits_limit
        & close_hits_limit
    ).astype(bool)
    return output_daily


def label_opened(
    daily_df: pd.DataFrame,
    instruments_df: pd.DataFrame,
    eps: float = DEFAULT_EPS,
    rules_path: str | Path | None = None,
) -> pd.DataFrame:
    _check_daily_columns(daily_df, ["high", "low", "trade_date", "ts_code", "pre_close"])
    output_daily = label_limit_up(daily_df, instruments_df, eps=eps, rules_path=rules_path)
    high_hits_limit = _is_close_to_limit(output_daily["high"], output_daily["limit_up_price"], eps=eps)
    low_below_limit = pd.to_numeric(output_daily["low"], errors="coerce") < (
        pd.to_numeric(output_daily["limit_up_price"], errors="coerce") - eps
    )
    output_daily["label_opened"] = (
        output_daily["price_limit_applicable"] & high_hits_limit & low_below_limit
    ).astype(bool)
    return output_daily


def label_sealed(
    daily_df: pd.DataFrame,
    instruments_df: pd.DataFrame,
    eps: float = DEFAULT_EPS,
    rules_path: str | Path | None = None,
) -> pd.DataFrame:
    output_daily = label_opened(daily_df, instruments_df, eps=eps, rules_path=rules_path)
    output_daily["label_sealed"] = (output_daily["label_limit_up"] & ~output_daily["label_opened"]).astype(
        bool
    )
    return output_daily
