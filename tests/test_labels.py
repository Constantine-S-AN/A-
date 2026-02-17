from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from limitup_lab.labels import (
    add_limit_prices,
    label_limit_up,
    label_one_word,
    label_opened,
    label_sealed,
)


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "limit_rules.toml"


def _build_daily_bars() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": "AAA",
                "trade_date": "20240102",
                "open": 11.00,
                "high": 11.00,
                "low": 11.00,
                "close": 11.00,
                "pre_close": 10.00,
                "vol": 1.0,
                "amount": 1.0,
            },
            {
                "ts_code": "AAA",
                "trade_date": "20240103",
                "open": 10.70,
                "high": 11.00,
                "low": 10.50,
                "close": 10.95,
                "pre_close": 10.00,
                "vol": 1.0,
                "amount": 1.0,
            },
            {
                "ts_code": "AAA",
                "trade_date": "20240104",
                "open": 10.50,
                "high": 10.80,
                "low": 10.30,
                "close": 10.70,
                "pre_close": 10.00,
                "vol": 1.0,
                "amount": 1.0,
            },
            {
                "ts_code": "BBB",
                "trade_date": "20240103",
                "open": 12.00,
                "high": 12.00,
                "low": 12.00,
                "close": 12.00,
                "pre_close": 10.00,
                "vol": 1.0,
                "amount": 1.0,
            },
            {
                "ts_code": "AAA",
                "trade_date": "20240105",
                "open": 10.90,
                "high": 11.00,
                "low": 11.00,
                "close": 11.00,
                "pre_close": 10.00,
                "vol": 1.0,
                "amount": 1.0,
            },
        ]
    )


def _build_instruments() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ts_code": "AAA", "board": "MAIN", "is_st": False, "list_date": None},
            {"ts_code": "BBB", "board": "STAR", "is_st": False, "list_date": "20240101"},
        ]
    )


def test_add_limit_prices_and_daily_labels() -> None:
    daily_bars = _build_daily_bars()
    instruments = _build_instruments()

    with_limit_prices = add_limit_prices(daily_bars, instruments, rules_path=CONFIG_PATH)
    assert with_limit_prices["limit_up_price"].tolist() == [11.0, 11.0, 11.0, 12.0, 11.0]

    with_limit_up_label = label_limit_up(daily_bars, instruments, rules_path=CONFIG_PATH)
    assert with_limit_up_label["label_limit_up"].tolist() == [True, False, False, False, True]

    with_one_word_label = label_one_word(daily_bars, instruments, rules_path=CONFIG_PATH)
    assert with_one_word_label["label_one_word"].tolist() == [True, False, False, False, False]

    with_opened_label = label_opened(daily_bars, instruments, rules_path=CONFIG_PATH)
    assert with_opened_label["label_opened"].tolist() == [False, True, False, False, False]

    with_sealed_label = label_sealed(daily_bars, instruments, rules_path=CONFIG_PATH)
    assert with_sealed_label["label_sealed"].tolist() == [True, False, False, False, True]


def test_labels_are_idempotent() -> None:
    daily_bars = _build_daily_bars()
    instruments = _build_instruments()

    first_pass = label_sealed(daily_bars, instruments, rules_path=CONFIG_PATH)
    second_pass = label_sealed(first_pass, instruments, rules_path=CONFIG_PATH)

    assert_frame_equal(
        first_pass[
            [
                "limit_up_price",
                "price_limit_applicable",
                "label_limit_up",
                "label_opened",
                "label_sealed",
            ]
        ],
        second_pass[
            [
                "limit_up_price",
                "price_limit_applicable",
                "label_limit_up",
                "label_opened",
                "label_sealed",
            ]
        ],
    )

