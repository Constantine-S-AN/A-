from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
import tomllib
from typing import Mapping


DEFAULT_LIMIT_RULES = {
    # 基线规则：主板一般 10%，风险警示(ST)一般 5%；上市初期按板块可有“无涨跌幅限制天数”。
    "MAIN": {"limit_up": 0.10, "limit_down": 0.10, "ipo_unlimited_days": 1},
    "ST": {"limit_up": 0.05, "limit_down": 0.05, "ipo_unlimited_days": 1},
    "STAR": {"limit_up": 0.20, "limit_down": 0.20, "ipo_unlimited_days": 5},
    "CHINEXT": {"limit_up": 0.20, "limit_down": 0.20, "ipo_unlimited_days": 5},
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_rules_path() -> Path:
    return _project_root() / "config" / "limit_rules.toml"


@lru_cache(maxsize=4)
def _load_rules(path: str) -> dict[str, dict[str, float | int]]:
    rules_path = Path(path)
    if not rules_path.exists():
        return DEFAULT_LIMIT_RULES

    loaded = tomllib.loads(rules_path.read_text(encoding="utf-8"))
    merged_rules = {key: value.copy() for key, value in DEFAULT_LIMIT_RULES.items()}
    for board, params in loaded.items():
        board_key = board.upper().strip()
        if board_key not in merged_rules:
            merged_rules[board_key] = {}
        merged_rules[board_key].update(params)
    return merged_rules


def _normalize_date(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None

    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date()

    for pattern in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {value}")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n", ""}:
        return False
    return bool(value)


def pick_limit_params(
    instrument_row: Mapping[str, object],
    rules_path: str | Path | None = None,
) -> tuple[Decimal, Decimal, int]:
    config_path = str(rules_path or _default_rules_path())
    limit_rules = _load_rules(config_path)

    board_name = str(instrument_row.get("board", "UNKNOWN")).strip().upper()
    is_st = _as_bool(instrument_row.get("is_st", False))
    board_key = "ST" if is_st else board_name
    if board_key not in limit_rules:
        board_key = "MAIN"

    board_params = limit_rules[board_key]
    limit_up = Decimal(str(board_params["limit_up"]))
    limit_down = Decimal(str(board_params["limit_down"]))
    ipo_unlimited_days = int(board_params["ipo_unlimited_days"])
    return limit_up, limit_down, ipo_unlimited_days


def compute_limit_price(pre_close: Decimal | float | int | str, up: Decimal | float | str) -> Decimal:
    pre_close_decimal = Decimal(str(pre_close))
    limit_up_decimal = Decimal(str(up))
    multiplier = Decimal("1") + limit_up_decimal
    return (pre_close_decimal * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_price_limit_applicable(
    instrument_row: Mapping[str, object],
    trade_date: str,
    rules_path: str | Path | None = None,
) -> bool:
    listing_date = _normalize_date(instrument_row.get("list_date"))
    if listing_date is None:
        return True

    current_trade_date = _normalize_date(trade_date)
    if current_trade_date is None:
        raise ValueError("trade_date 不能为空")

    _, _, ipo_unlimited_days = pick_limit_params(instrument_row, rules_path=rules_path)
    listing_age_days = (current_trade_date - listing_date).days
    return listing_age_days >= ipo_unlimited_days
