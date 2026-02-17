from __future__ import annotations

from pathlib import Path

import pandas as pd

from limitup_lab.streaks import compute_limitup_streak, exclude_suspended, exclude_unlimited_days


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "limit_rules.toml"


def test_compute_limitup_streak_two_symbols_six_days() -> None:
    daily_bars = pd.DataFrame(
        [
            {"ts_code": "AAA", "trade_date": "20240102", "label_limit_up": True},
            {"ts_code": "BBB", "trade_date": "20240102", "label_limit_up": False},
            {"ts_code": "AAA", "trade_date": "20240103", "label_limit_up": True},
            {"ts_code": "BBB", "trade_date": "20240103", "label_limit_up": True},
            {"ts_code": "AAA", "trade_date": "20240104", "label_limit_up": False},
            {"ts_code": "BBB", "trade_date": "20240104", "label_limit_up": True},
            {"ts_code": "AAA", "trade_date": "20240105", "label_limit_up": True},
            {"ts_code": "BBB", "trade_date": "20240105", "label_limit_up": True},
            {"ts_code": "AAA", "trade_date": "20240108", "label_limit_up": True},
            {"ts_code": "BBB", "trade_date": "20240108", "label_limit_up": False},
            {"ts_code": "AAA", "trade_date": "20240109", "label_limit_up": True},
            {"ts_code": "BBB", "trade_date": "20240109", "label_limit_up": True},
        ]
    )

    with_streak = compute_limitup_streak(daily_bars).sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

    aaa_streak = with_streak.loc[with_streak["ts_code"] == "AAA", "streak_up"].tolist()
    bbb_streak = with_streak.loc[with_streak["ts_code"] == "BBB", "streak_up"].tolist()
    assert aaa_streak == [1, 2, 0, 1, 2, 3]
    assert bbb_streak == [0, 1, 2, 3, 0, 1]


def test_compute_limitup_streak_breaks_on_missing_symbol_trade_day() -> None:
    daily_bars = pd.DataFrame(
        [
            {"ts_code": "AAA", "trade_date": "20240102", "label_limit_up": True},
            {"ts_code": "AAA", "trade_date": "20240104", "label_limit_up": True},
            {"ts_code": "BBB", "trade_date": "20240102", "label_limit_up": False},
            {"ts_code": "BBB", "trade_date": "20240103", "label_limit_up": False},
            {"ts_code": "BBB", "trade_date": "20240104", "label_limit_up": False},
        ]
    )

    with_streak = compute_limitup_streak(daily_bars).sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    aaa_streak = with_streak.loc[with_streak["ts_code"] == "AAA", "streak_up"].tolist()
    assert aaa_streak == [1, 1]


def test_exclude_filters() -> None:
    daily_bars = pd.DataFrame(
        [
            {"ts_code": "AAA", "trade_date": "20240102", "vol": 100.0},
            {"ts_code": "BBB", "trade_date": "20240103", "vol": 120.0},
            {"ts_code": "BBB", "trade_date": "20240106", "vol": 0.0},
            {"ts_code": "BBB", "trade_date": "20240107", "vol": 130.0},
        ]
    )
    instruments = pd.DataFrame(
        [
            {"ts_code": "AAA", "board": "MAIN", "is_st": False, "list_date": None},
            {"ts_code": "BBB", "board": "STAR", "is_st": False, "list_date": "20240101"},
        ]
    )

    filtered_unlimited = exclude_unlimited_days(daily_bars, instruments_df=instruments, rules_path=CONFIG_PATH)
    assert filtered_unlimited[["ts_code", "trade_date"]].to_dict(orient="records") == [
        {"ts_code": "AAA", "trade_date": "20240102"},
        {"ts_code": "BBB", "trade_date": "20240106"},
        {"ts_code": "BBB", "trade_date": "20240107"},
    ]

    filtered_active = exclude_suspended(filtered_unlimited)
    assert filtered_active[["ts_code", "trade_date"]].to_dict(orient="records") == [
        {"ts_code": "AAA", "trade_date": "20240102"},
        {"ts_code": "BBB", "trade_date": "20240107"},
    ]

