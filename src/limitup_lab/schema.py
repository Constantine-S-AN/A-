from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Board(str, Enum):
    MAIN = "MAIN"
    STAR = "STAR"
    CHINEXT = "CHINEXT"
    BSE = "BSE"
    UNKNOWN = "UNKNOWN"


class DailyBar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ts_code: str = Field(min_length=1)
    trade_date: str = Field(pattern=r"^\d{8}$")
    open: float
    high: float
    low: float
    close: float
    pre_close: float
    vol: float
    amount: float

    @field_validator("trade_date")
    @classmethod
    def validate_trade_date(cls, trade_date: str) -> str:
        datetime.strptime(trade_date, "%Y%m%d")
        return trade_date


class Instrument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ts_code: str = Field(min_length=1)
    name: str | None = None
    board: Board
    is_st: bool
    list_date: str | None = None

    @field_validator("list_date")
    @classmethod
    def validate_list_date(cls, list_date: str | None) -> str | None:
        if list_date is None:
            return None
        datetime.strptime(list_date, "%Y%m%d")
        return list_date


DAILY_BAR_COLUMNS = list(DailyBar.model_fields.keys())
INSTRUMENT_COLUMNS = list(Instrument.model_fields.keys())

REQUIRED_DAILY_BAR_COLUMNS = [
    column_name
    for column_name, field_info in DailyBar.model_fields.items()
    if field_info.is_required()
]
REQUIRED_INSTRUMENT_COLUMNS = [
    column_name
    for column_name, field_info in Instrument.model_fields.items()
    if field_info.is_required()
]

