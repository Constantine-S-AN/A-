from __future__ import annotations

from pathlib import Path
from typing import Type

import pandas as pd
from pydantic import BaseModel, TypeAdapter, ValidationError

from limitup_lab.schema import (
    DAILY_BAR_COLUMNS,
    INSTRUMENT_COLUMNS,
    DailyBar,
    Instrument,
    REQUIRED_DAILY_BAR_COLUMNS,
    REQUIRED_INSTRUMENT_COLUMNS,
)

DAILY_BAR_COLUMN_ALIASES = {
    "symbol": "ts_code",
    "code": "ts_code",
    "date": "trade_date",
    "prev_close": "pre_close",
    "preclose": "pre_close",
    "volume": "vol",
    "turnover": "amount",
    "amt": "amount",
}

INSTRUMENT_COLUMN_ALIASES = {
    "symbol": "ts_code",
    "code": "ts_code",
    "st": "is_st",
    "isst": "is_st",
    "ipo_date": "list_date",
    "listing_date": "list_date",
}


def _read_table(path: str | Path) -> pd.DataFrame:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"文件不存在: {input_path}")

    extension = input_path.suffix.lower()
    if extension == ".csv":
        return pd.read_csv(input_path)
    if extension in {".parquet", ".pq"}:
        return pd.read_parquet(input_path)
    raise ValueError(f"仅支持 CSV 或 Parquet 文件: {input_path}")


def _normalize_column_names(
    dataframe: pd.DataFrame,
    column_aliases: dict[str, str],
) -> pd.DataFrame:
    normalized_column_map = {
        column_name: str(column_name).strip().lower() for column_name in dataframe.columns
    }
    normalized_dataframe = dataframe.rename(columns=normalized_column_map)
    return normalized_dataframe.rename(columns=column_aliases)


def _check_missing_columns(dataframe: pd.DataFrame, required_columns: list[str]) -> None:
    missing_columns = [column_name for column_name in required_columns if column_name not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"缺失必要列: {missing_columns}")


def _normalize_trade_dates(date_series: pd.Series, allow_empty: bool = False) -> pd.Series:
    date_text = date_series.astype("string").str.strip()
    missing_mask = date_text.isna() | date_text.eq("") | date_text.str.lower().eq("nan")
    if allow_empty:
        normalized_dates = pd.Series([None] * len(date_text), index=date_text.index, dtype="object")
        non_empty_mask = ~missing_mask
        if non_empty_mask.any():
            normalized_non_empty = _normalize_trade_dates(date_text[non_empty_mask], allow_empty=False)
            normalized_dates.loc[non_empty_mask] = normalized_non_empty
        return normalized_dates

    normalized_dates = pd.Series(index=date_text.index, dtype="object")
    digit_date_mask = date_text.str.fullmatch(r"\d{8}")

    if digit_date_mask.any():
        parsed_digit_dates = pd.to_datetime(date_text[digit_date_mask], format="%Y%m%d", errors="coerce")
        normalized_dates.loc[digit_date_mask] = parsed_digit_dates.dt.strftime("%Y%m%d")

    non_digit_date_mask = ~digit_date_mask
    if non_digit_date_mask.any():
        parsed_non_digit_dates = pd.to_datetime(date_text[non_digit_date_mask], errors="coerce")
        normalized_dates.loc[non_digit_date_mask] = parsed_non_digit_dates.dt.strftime("%Y%m%d")

    invalid_mask = normalized_dates.isna()
    if invalid_mask.any():
        invalid_examples = date_text[invalid_mask].head(3).tolist()
        raise ValueError(f"日期格式非法，必须是 YYYYMMDD 或可解析日期: {invalid_examples}")
    return normalized_dates


def _coerce_numeric_columns(dataframe: pd.DataFrame, numeric_columns: list[str]) -> pd.DataFrame:
    coerced_frame = dataframe.copy()
    for column_name in numeric_columns:
        coerced_frame[column_name] = pd.to_numeric(coerced_frame[column_name], errors="coerce")
        invalid_mask = coerced_frame[column_name].isna()
        if invalid_mask.any():
            invalid_examples = dataframe.loc[invalid_mask, column_name].head(3).tolist()
            raise ValueError(f"列 {column_name} 存在无法转换为数值的内容: {invalid_examples}")
        coerced_frame[column_name] = coerced_frame[column_name].astype(float)
    return coerced_frame


def _coerce_bool_series(bool_series: pd.Series) -> pd.Series:
    true_values = {"1", "true", "t", "yes", "y"}
    false_values = {"0", "false", "f", "no", "n"}

    bool_text = bool_series.astype("string").str.strip().str.lower()
    mapped_bool = bool_text.map(
        lambda text_value: True
        if text_value in true_values
        else False
        if text_value in false_values
        else pd.NA
    )
    invalid_mask = mapped_bool.isna()
    if invalid_mask.any():
        invalid_examples = bool_series[invalid_mask].head(3).tolist()
        raise ValueError(f"is_st 列包含无法识别的布尔值: {invalid_examples}")
    return mapped_bool.astype(bool)


def _validate_rows_with_model(dataframe: pd.DataFrame, model_class: Type[BaseModel]) -> pd.DataFrame:
    records = dataframe.where(pd.notna(dataframe), None).to_dict(orient="records")
    try:
        validator = TypeAdapter(list[model_class])
        validated_records = validator.validate_python(records)
    except ValidationError as validation_error:
        raise ValueError(f"Schema 校验失败: {validation_error}") from validation_error
    normalized_records = [record.model_dump(mode="json") for record in validated_records]
    canonical_columns = list(model_class.model_fields.keys())
    return pd.DataFrame(normalized_records, columns=canonical_columns)


def read_daily_bars(path: str | Path) -> pd.DataFrame:
    daily_bars = _read_table(path)
    daily_bars = _normalize_column_names(daily_bars, DAILY_BAR_COLUMN_ALIASES)
    _check_missing_columns(daily_bars, REQUIRED_DAILY_BAR_COLUMNS)

    canonical_daily_bars = daily_bars.loc[:, DAILY_BAR_COLUMNS].copy()
    canonical_daily_bars["ts_code"] = canonical_daily_bars["ts_code"].astype("string").str.strip()
    canonical_daily_bars["trade_date"] = _normalize_trade_dates(canonical_daily_bars["trade_date"])
    numeric_columns = ["open", "high", "low", "close", "pre_close", "vol", "amount"]
    canonical_daily_bars = _coerce_numeric_columns(canonical_daily_bars, numeric_columns)

    return _validate_rows_with_model(canonical_daily_bars, DailyBar)


def read_instruments(path: str | Path) -> pd.DataFrame:
    instruments = _read_table(path)
    instruments = _normalize_column_names(instruments, INSTRUMENT_COLUMN_ALIASES)
    _check_missing_columns(instruments, REQUIRED_INSTRUMENT_COLUMNS)

    canonical_instruments = instruments.copy()
    for optional_column in ["name", "list_date"]:
        if optional_column not in canonical_instruments.columns:
            canonical_instruments[optional_column] = None
    canonical_instruments = canonical_instruments.loc[:, INSTRUMENT_COLUMNS].copy()

    canonical_instruments["ts_code"] = canonical_instruments["ts_code"].astype("string").str.strip()
    canonical_instruments["name"] = canonical_instruments["name"].astype("string").str.strip()
    canonical_instruments["board"] = (
        canonical_instruments["board"].astype("string").str.strip().str.upper()
    )
    canonical_instruments["is_st"] = _coerce_bool_series(canonical_instruments["is_st"])
    canonical_instruments["list_date"] = _normalize_trade_dates(
        canonical_instruments["list_date"], allow_empty=True
    )

    return _validate_rows_with_model(canonical_instruments, Instrument)


def write_parquet(dataframe: pd.DataFrame, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        dataframe.to_parquet(output_path, index=False)
    except ImportError as import_error:
        raise RuntimeError("写入 parquet 需要安装 pyarrow 或 fastparquet") from import_error
