from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from limitup_lab.limits import compute_limit_price, is_price_limit_applicable, pick_limit_params


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "limit_rules.toml"


def test_compute_limit_price_main_board_rounds_to_cent() -> None:
    limit_price = compute_limit_price(pre_close=10, up=Decimal("0.10"))
    assert limit_price == Decimal("11.00")


def test_pick_limit_params_respects_st_rule() -> None:
    up_limit, down_limit, ipo_days = pick_limit_params(
        {"board": "MAIN", "is_st": True},
        rules_path=CONFIG_PATH,
    )
    assert up_limit == Decimal("0.05")
    assert down_limit == Decimal("0.05")
    assert ipo_days == 1


def test_is_price_limit_applicable_uses_listing_age() -> None:
    instrument = {"board": "STAR", "is_st": False, "list_date": "20240101"}
    assert not is_price_limit_applicable(instrument, "20240105", rules_path=CONFIG_PATH)
    assert is_price_limit_applicable(instrument, "20240106", rules_path=CONFIG_PATH)


def test_is_price_limit_applicable_defaults_true_when_list_date_missing() -> None:
    instrument = {"board": "MAIN", "is_st": False, "list_date": None}
    assert is_price_limit_applicable(instrument, "20240102", rules_path=CONFIG_PATH)

