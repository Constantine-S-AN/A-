from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd

from limitup_lab.adapters.akshare import (
    fetch_akshare_daily_bars,
    fetch_akshare_instruments,
    infer_board,
    parse_ts_code,
    to_ak_symbol,
)


def test_parse_ts_code_and_symbol_mapping() -> None:
    code, exchange = parse_ts_code("002261.SZ")
    assert code == "002261"
    assert exchange == "SZ"
    assert to_ak_symbol("603598.SH") == "603598"


def test_infer_board_from_ts_code() -> None:
    assert infer_board("688256.SH") == "STAR"
    assert infer_board("300418.SZ") == "CHINEXT"
    assert infer_board("430047.BJ") == "BSE"
    assert infer_board("002261.SZ") == "MAIN"


def test_fetch_akshare_daily_bars_with_mocked_module(monkeypatch) -> None:
    def fake_stock_zh_a_hist(
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        assert period == "daily"
        assert start_date == "20240301"
        assert end_date == "20240307"
        if symbol == "002261":
            return pd.DataFrame(
                [
                    {
                        "日期": "2024-03-01",
                        "开盘": 10.00,
                        "收盘": 10.20,
                        "最高": 10.30,
                        "最低": 9.90,
                        "成交量": 100000,
                        "成交额": 1020000,
                    },
                    {
                        "日期": "2024-03-04",
                        "开盘": 10.40,
                        "收盘": 11.22,
                        "最高": 11.22,
                        "最低": 10.30,
                        "成交量": 120000,
                        "成交额": 1300000,
                    },
                ]
            )
        return pd.DataFrame()

    fake_akshare = SimpleNamespace(
        stock_zh_a_hist=fake_stock_zh_a_hist,
        stock_zh_a_spot_em=lambda: pd.DataFrame(columns=["代码", "名称"]),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    daily_bars = fetch_akshare_daily_bars(
        ts_codes=["002261.SZ"],
        start_date="20240301",
        end_date="20240307",
        adjust="",
    )

    assert list(daily_bars.columns) == [
        "ts_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "vol",
        "amount",
    ]
    assert len(daily_bars) == 1
    row = daily_bars.iloc[0]
    assert row["ts_code"] == "002261.SZ"
    assert row["trade_date"] == "20240304"
    assert float(row["pre_close"]) == 10.20


def test_fetch_akshare_instruments_with_mocked_spot(monkeypatch) -> None:
    fake_akshare = SimpleNamespace(
        stock_zh_a_hist=lambda **_: pd.DataFrame(),
        stock_zh_a_spot_em=lambda: pd.DataFrame(
            [
                {"代码": "002261", "名称": "拓维信息"},
                {"代码": "603598", "名称": "*ST传媒"},
            ]
        ),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    instruments = fetch_akshare_instruments(["002261.SZ", "603598.SH"], include_names=True)
    assert instruments["name"].tolist() == ["拓维信息", "*ST传媒"]
    assert instruments["board"].tolist() == ["MAIN", "MAIN"]
    assert instruments["is_st"].tolist() == [False, True]


def test_fetch_akshare_instruments_without_names() -> None:
    instruments = fetch_akshare_instruments(["002261.SZ", "688256.SH"], include_names=False)
    assert instruments["name"].isna().all()
    assert instruments["board"].tolist() == ["MAIN", "STAR"]
    assert instruments["is_st"].tolist() == [False, False]
