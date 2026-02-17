from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from limitup_lab.io import read_daily_bars, read_instruments
from limitup_lab.schema import DAILY_BAR_COLUMNS, INSTRUMENT_COLUMNS


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def test_read_daily_bars_aligns_columns_and_types() -> None:
    daily_bars = read_daily_bars(FIXTURE_DIR / "daily_bars.csv")

    assert list(daily_bars.columns) == DAILY_BAR_COLUMNS
    assert daily_bars["trade_date"].tolist() == ["20240102", "20240103"]
    assert pd.api.types.is_object_dtype(daily_bars["ts_code"])
    for numeric_column in ["open", "high", "low", "close", "pre_close", "vol", "amount"]:
        assert pd.api.types.is_float_dtype(daily_bars[numeric_column])


def test_read_daily_bars_missing_required_columns_raises() -> None:
    with pytest.raises(ValueError, match="缺失必要列"):
        read_daily_bars(FIXTURE_DIR / "daily_bars_missing.csv")


def test_read_instruments_aligns_columns_and_types() -> None:
    instruments = read_instruments(FIXTURE_DIR / "instruments.csv")

    assert list(instruments.columns) == INSTRUMENT_COLUMNS
    assert instruments["board"].tolist() == ["MAIN", "STAR", "BSE"]
    assert pd.api.types.is_bool_dtype(instruments["is_st"])
    assert instruments["list_date"].tolist() == ["19910403", "20190722", None]

