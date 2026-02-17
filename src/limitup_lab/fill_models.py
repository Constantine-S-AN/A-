from __future__ import annotations

from enum import Enum
from typing import Mapping

import pandas as pd


class FillModel(str, Enum):
    IDEAL = "IDEAL"
    CONSERVATIVE = "CONSERVATIVE"


def _normalize_model(model: FillModel | str) -> FillModel:
    if isinstance(model, FillModel):
        return model
    return FillModel(str(model).strip().upper())


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n", "", "nan"}:
        return False
    return bool(value)


def _get_flag(row: Mapping[str, object], primary_key: str, alias_key: str | None = None) -> bool:
    if primary_key in row:
        return _as_bool(row[primary_key])
    if alias_key is not None and alias_key in row:
        return _as_bool(row[alias_key])
    return False


def can_buy_limitup_day(row: Mapping[str, object], model: FillModel | str) -> bool:
    fill_model = _normalize_model(model)
    is_limit_up = _get_flag(row, "label_limit_up", alias_key="is_limit_up")
    if not is_limit_up:
        return False

    if fill_model == FillModel.IDEAL:
        return True

    is_sealed = _get_flag(row, "label_sealed", alias_key="sealed")
    is_one_word = _get_flag(row, "label_one_word", alias_key="one_word")
    return not (is_sealed or is_one_word)


def entry_price(row: Mapping[str, object], model: FillModel | str) -> float:
    _normalize_model(model)
    if "close" not in row:
        raise ValueError("row 缺少 close 列，无法计算 entry_price")

    close_price = pd.to_numeric(pd.Series([row["close"]]), errors="coerce").iloc[0]
    if pd.isna(close_price):
        raise ValueError("close 不是有效数字，无法计算 entry_price")
    return float(close_price)

