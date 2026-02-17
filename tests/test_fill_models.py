from __future__ import annotations

import pytest

from limitup_lab.fill_models import FillModel, can_buy_limitup_day, entry_price


def test_conservative_cannot_buy_sealed_or_one_word() -> None:
    sealed_row = {
        "label_limit_up": True,
        "label_sealed": True,
        "label_one_word": False,
        "close": 11.0,
    }
    one_word_row = {
        "label_limit_up": True,
        "label_sealed": False,
        "label_one_word": True,
        "close": 11.0,
    }
    opened_row = {
        "label_limit_up": True,
        "label_sealed": False,
        "label_one_word": False,
        "close": 10.9,
    }

    assert not can_buy_limitup_day(sealed_row, FillModel.CONSERVATIVE)
    assert not can_buy_limitup_day(one_word_row, FillModel.CONSERVATIVE)
    assert can_buy_limitup_day(opened_row, FillModel.CONSERVATIVE)


def test_ideal_can_buy_limitup_day_even_when_sealed() -> None:
    sealed_row = {
        "label_limit_up": True,
        "label_sealed": True,
        "label_one_word": True,
        "close": 11.0,
    }
    assert can_buy_limitup_day(sealed_row, FillModel.IDEAL)


def test_cannot_buy_if_not_limit_up() -> None:
    non_limit_row = {"label_limit_up": False, "close": 10.5}
    assert not can_buy_limitup_day(non_limit_row, FillModel.IDEAL)
    assert not can_buy_limitup_day(non_limit_row, FillModel.CONSERVATIVE)


def test_entry_price_uses_close_for_all_models() -> None:
    row = {"close": "10.88"}
    assert entry_price(row, FillModel.IDEAL) == pytest.approx(10.88)
    assert entry_price(row, FillModel.CONSERVATIVE) == pytest.approx(10.88)

