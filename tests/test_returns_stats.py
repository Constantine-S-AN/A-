from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from limitup_lab.returns import add_next_day_returns
from limitup_lab.stats import group_stats


def test_add_next_day_returns_computes_forward_premium() -> None:
    daily_bars = pd.DataFrame(
        [
            {"ts_code": "AAA", "trade_date": "20240103", "open": 11.0, "close": 12.0},
            {"ts_code": "AAA", "trade_date": "20240102", "open": 10.0, "close": 10.0},
            {"ts_code": "BBB", "trade_date": "20240102", "open": 20.0, "close": 20.0},
            {"ts_code": "BBB", "trade_date": "20240103", "open": 19.0, "close": 18.0},
        ]
    )

    with_returns = add_next_day_returns(daily_bars)

    assert with_returns[["ts_code", "trade_date"]].to_dict(orient="records") == daily_bars[
        ["ts_code", "trade_date"]
    ].to_dict(orient="records")

    aaa_day1 = with_returns[(with_returns["ts_code"] == "AAA") & (with_returns["trade_date"] == "20240102")].iloc[
        0
    ]
    aaa_day2 = with_returns[(with_returns["ts_code"] == "AAA") & (with_returns["trade_date"] == "20240103")].iloc[
        0
    ]
    bbb_day1 = with_returns[(with_returns["ts_code"] == "BBB") & (with_returns["trade_date"] == "20240102")].iloc[
        0
    ]
    bbb_day2 = with_returns[(with_returns["ts_code"] == "BBB") & (with_returns["trade_date"] == "20240103")].iloc[
        0
    ]

    assert np.isclose(aaa_day1["next_open_ret"], 0.10)
    assert np.isclose(aaa_day1["next_close_ret"], 0.20)
    assert np.isnan(aaa_day2["next_open_ret"])
    assert np.isnan(aaa_day2["next_close_ret"])

    assert np.isclose(bbb_day1["next_open_ret"], -0.05)
    assert np.isclose(bbb_day1["next_close_ret"], -0.10)
    assert np.isnan(bbb_day2["next_open_ret"])
    assert np.isnan(bbb_day2["next_close_ret"])


def test_group_stats_stable_with_default_group_columns() -> None:
    labeled_rows = pd.DataFrame(
        [
            {
                "board": "MAIN",
                "is_st": False,
                "streak_up": 2,
                "label_one_word": True,
                "label_opened": False,
                "next_open_ret": 0.10,
                "next_close_ret": 0.20,
            },
            {
                "board": "MAIN",
                "is_st": False,
                "streak_up": 2,
                "label_one_word": True,
                "label_opened": False,
                "next_open_ret": 0.10,
                "next_close_ret": 0.20,
            },
            {
                "board": "STAR",
                "is_st": False,
                "streak_up": 1,
                "label_one_word": False,
                "label_opened": True,
                "next_open_ret": -0.05,
                "next_close_ret": -0.10,
            },
        ]
    )

    shuffled_rows = labeled_rows.sample(frac=1.0, random_state=7).reset_index(drop=True)
    stats_from_original = group_stats(labeled_rows)
    stats_from_shuffled = group_stats(shuffled_rows)
    assert_frame_equal(stats_from_original, stats_from_shuffled)

    assert stats_from_original["count"].tolist() == [2, 1]
    assert stats_from_original["next_open_ret_mean"].tolist() == [0.10, -0.05]
    assert stats_from_original["next_open_ret_p10"].tolist() == [0.10, -0.05]
    assert stats_from_original["next_open_ret_p50"].tolist() == [0.10, -0.05]
    assert stats_from_original["next_open_ret_p90"].tolist() == [0.10, -0.05]
    assert stats_from_original["next_close_ret_mean"].tolist() == [0.20, -0.10]
    assert stats_from_original["next_close_ret_p10"].tolist() == [0.20, -0.10]
    assert stats_from_original["next_close_ret_p50"].tolist() == [0.20, -0.10]
    assert stats_from_original["next_close_ret_p90"].tolist() == [0.20, -0.10]
