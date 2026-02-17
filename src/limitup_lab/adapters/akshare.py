from __future__ import annotations

from datetime import datetime
from types import ModuleType

import pandas as pd

from limitup_lab.schema import DAILY_BAR_COLUMNS, INSTRUMENT_COLUMNS


def _import_akshare() -> ModuleType:
    try:
        import akshare as ak
    except ImportError as exc:  # pragma: no cover - depends on optional runtime dependency.
        raise RuntimeError(
            "未安装 akshare。请先执行: pip install akshare"
        ) from exc
    return ak


def parse_ts_code(ts_code: str) -> tuple[str, str]:
    normalized = str(ts_code).strip().upper()
    if "." not in normalized:
        raise ValueError(f"ts_code 格式非法: {ts_code}")
    code, exchange = normalized.split(".", 1)
    if not code.isdigit() or len(code) != 6:
        raise ValueError(f"ts_code 代码段非法: {ts_code}")
    if exchange not in {"SZ", "SH", "BJ"}:
        raise ValueError(f"ts_code 交易所非法: {ts_code}")
    return code, exchange


def to_ak_symbol(ts_code: str) -> str:
    code, _ = parse_ts_code(ts_code)
    return code


def infer_board(ts_code: str) -> str:
    code, exchange = parse_ts_code(ts_code)
    if exchange == "SH" and code.startswith("688"):
        return "STAR"
    if exchange == "SZ" and code.startswith("300"):
        return "CHINEXT"
    if exchange == "BJ":
        return "BSE"
    return "MAIN"


def _validate_trade_date(text: str, field_name: str) -> str:
    normalized = str(text).strip()
    datetime.strptime(normalized, "%Y%m%d")
    return normalized


def _extract_name_map(ak: ModuleType) -> dict[str, str]:
    try:
        spot_frame = ak.stock_zh_a_spot_em()
    except Exception:
        return {}
    if not isinstance(spot_frame, pd.DataFrame):
        return {}
    if "代码" not in spot_frame.columns or "名称" not in spot_frame.columns:
        return {}
    non_empty_spot = spot_frame.loc[
        spot_frame["代码"].notna() & spot_frame["名称"].notna(), ["代码", "名称"]
    ].copy()
    non_empty_spot["代码"] = non_empty_spot["代码"].astype("string").str.strip()
    non_empty_spot["名称"] = non_empty_spot["名称"].astype("string").str.strip()
    return dict(zip(non_empty_spot["代码"], non_empty_spot["名称"], strict=False))


def fetch_akshare_daily_bars(
    ts_codes: list[str],
    start_date: str,
    end_date: str,
    adjust: str = "",
) -> pd.DataFrame:
    ak = _import_akshare()
    normalized_start = _validate_trade_date(start_date, "start_date")
    normalized_end = _validate_trade_date(end_date, "end_date")

    daily_frames: list[pd.DataFrame] = []
    for ts_code in ts_codes:
        symbol = to_ak_symbol(ts_code)
        raw_frame = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=normalized_start,
            end_date=normalized_end,
            adjust=adjust,
        )
        if not isinstance(raw_frame, pd.DataFrame) or raw_frame.empty:
            continue

        required_columns = {"日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"}
        if not required_columns.issubset(set(raw_frame.columns)):
            missing_columns = sorted(required_columns.difference(set(raw_frame.columns)))
            raise RuntimeError(f"akshare 返回缺列: {missing_columns}")

        normalized_frame = raw_frame.loc[:, ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]].copy()
        normalized_frame = normalized_frame.rename(
            columns={
                "日期": "trade_date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "vol",
                "成交额": "amount",
            }
        )
        normalized_frame["trade_date"] = pd.to_datetime(
            normalized_frame["trade_date"], errors="coerce"
        ).dt.strftime("%Y%m%d")
        normalized_frame = normalized_frame.dropna(subset=["trade_date"]).sort_values("trade_date")
        normalized_frame["pre_close"] = pd.to_numeric(
            normalized_frame["close"], errors="coerce"
        ).shift(1)
        normalized_frame["ts_code"] = ts_code

        numeric_columns = ["open", "high", "low", "close", "pre_close", "vol", "amount"]
        for column_name in numeric_columns:
            normalized_frame[column_name] = pd.to_numeric(normalized_frame[column_name], errors="coerce")

        normalized_frame = normalized_frame.dropna(subset=numeric_columns)
        if normalized_frame.empty:
            continue
        daily_frames.append(normalized_frame.loc[:, DAILY_BAR_COLUMNS])

    if not daily_frames:
        raise RuntimeError("未获取到任何日线数据，请检查 symbols 或日期区间。")
    return pd.concat(daily_frames, ignore_index=True)


def fetch_akshare_instruments(ts_codes: list[str], include_names: bool = False) -> pd.DataFrame:
    name_map: dict[str, str] = {}
    if include_names:
        ak = _import_akshare()
        name_map = _extract_name_map(ak)

    instrument_rows: list[dict[str, object]] = []
    for ts_code in ts_codes:
        code, _ = parse_ts_code(ts_code)
        stock_name = name_map.get(code)
        instrument_rows.append(
            {
                "ts_code": ts_code,
                "name": stock_name,
                "board": infer_board(ts_code),
                "is_st": bool(stock_name and "ST" in stock_name.upper()),
                "list_date": None,
            }
        )
    return pd.DataFrame(instrument_rows, columns=INSTRUMENT_COLUMNS)


def fetch_akshare_dataset(
    ts_codes: list[str],
    start_date: str,
    end_date: str,
    adjust: str = "",
    include_names: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    normalized_ts_codes = [str(ts_code).strip().upper() for ts_code in ts_codes if str(ts_code).strip()]
    if not normalized_ts_codes:
        raise ValueError("symbols 不能为空。示例: 002261.SZ,603598.SH")

    daily_bars = fetch_akshare_daily_bars(
        ts_codes=normalized_ts_codes,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
    instruments = fetch_akshare_instruments(normalized_ts_codes, include_names=include_names)
    return daily_bars, instruments
