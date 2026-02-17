from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from limitup_lab.fill_models import FillModel, entry_price
from limitup_lab.strategy_base import Strategy, ensure_columns, normalize_bool_series, parse_trade_dates


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity_curve: pd.DataFrame


def _normalize_fill_model(fill_model: FillModel | str) -> FillModel:
    if isinstance(fill_model, FillModel):
        return fill_model
    return FillModel(str(fill_model).strip().upper())


def _normalize_trade_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y%m%d")


def _build_price_lookup(daily_df: pd.DataFrame) -> pd.DataFrame:
    with_sort_key = daily_df.copy()
    with_sort_key["_trade_sort_key"] = parse_trade_dates(with_sort_key["trade_date"])
    with_sort_key["trade_date_norm"] = with_sort_key["_trade_sort_key"].dt.strftime("%Y%m%d")
    with_sort_key["_row_order"] = range(len(with_sort_key))
    with_sort_key = with_sort_key.sort_values(["ts_code", "_trade_sort_key", "_row_order"])
    with_sort_key = with_sort_key.drop_duplicates(
        subset=["ts_code", "trade_date_norm"],
        keep="last",
    )
    return with_sort_key.set_index(["ts_code", "trade_date_norm"])[["open", "close"]]


def _generate_signals(
    daily_df: pd.DataFrame,
    strategy: Strategy,
    fill_model: FillModel,
) -> tuple[pd.Series, pd.Series]:
    original_fill_model = getattr(strategy, "fill_model", None)
    has_fill_model = hasattr(strategy, "fill_model")
    if has_fill_model:
        setattr(strategy, "fill_model", fill_model)
    try:
        entry_signal = strategy.generate_entries(daily_df)
        exit_signal = strategy.generate_exits(daily_df)
    finally:
        if has_fill_model:
            setattr(strategy, "fill_model", original_fill_model)

    if len(entry_signal) != len(daily_df):
        raise ValueError("策略 entry 信号长度与输入数据不一致")
    if len(exit_signal) != len(daily_df):
        raise ValueError("策略 exit 信号长度与输入数据不一致")

    normalized_entry_signal = normalize_bool_series(pd.Series(entry_signal, index=daily_df.index))
    normalized_exit_signal = pd.Series(exit_signal, index=daily_df.index)
    return normalized_entry_signal, normalized_exit_signal


def _build_equity_curve(daily_df: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    trade_dates = (
        parse_trade_dates(daily_df["trade_date"])
        .dt.strftime("%Y%m%d")
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    equity = 1.0
    equity_rows: list[dict[str, Any]] = []
    for trade_date in trade_dates:
        if not trades.empty:
            day_returns = trades.loc[trades["exit_date"] == trade_date, "ret_net"]
            for day_return in day_returns:
                equity *= 1.0 + float(day_return)
        equity_rows.append({"trade_date": trade_date, "equity": equity})
    return pd.DataFrame(equity_rows)


def run_backtest(
    daily_df: pd.DataFrame,
    strategy: Strategy,
    fill_model: FillModel | str,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> BacktestResult:
    ensure_columns(daily_df, ["ts_code", "trade_date", "open", "close"])
    normalized_fill_model = _normalize_fill_model(fill_model)

    working_daily = daily_df.copy()
    working_daily["trade_date"] = parse_trade_dates(working_daily["trade_date"]).dt.strftime("%Y%m%d")

    entry_signal, exit_signal = _generate_signals(working_daily, strategy, normalized_fill_model)
    price_lookup = _build_price_lookup(working_daily)
    total_cost_bps = float(fee_bps) + float(slippage_bps)

    trade_records: list[dict[str, Any]] = []
    for row_index in working_daily.index[entry_signal]:
        entry_row = working_daily.loc[row_index]
        exit_date = _normalize_trade_date(exit_signal.loc[row_index])
        if exit_date is None:
            continue

        stock_code = str(entry_row["ts_code"]).strip()
        lookup_key = (stock_code, exit_date)
        if lookup_key not in price_lookup.index:
            continue

        entry_date = str(entry_row["trade_date"])
        entry_base_price = entry_price(entry_row.to_dict(), normalized_fill_model)
        exit_price_type = getattr(strategy, "exit_price_type", "next_close")
        exit_price_column = "open" if exit_price_type == "next_open" else "close"
        exit_base_price = float(price_lookup.loc[lookup_key, exit_price_column])

        entry_trade_price = entry_base_price * (1.0 + total_cost_bps / 10000.0)
        exit_trade_price = exit_base_price * (1.0 - total_cost_bps / 10000.0)
        net_return = exit_trade_price / entry_trade_price - 1.0

        trade_records.append(
            {
                "strategy_name": strategy.name,
                "fill_model": normalized_fill_model.value,
                "ts_code": stock_code,
                "entry_date": entry_date,
                "entry_price": entry_trade_price,
                "exit_date": exit_date,
                "exit_price": exit_trade_price,
                "ret_net": net_return,
            }
        )

    trades = pd.DataFrame(
        trade_records,
        columns=[
            "strategy_name",
            "fill_model",
            "ts_code",
            "entry_date",
            "entry_price",
            "exit_date",
            "exit_price",
            "ret_net",
        ],
    )
    if not trades.empty:
        trades = trades.sort_values(["entry_date", "ts_code"]).reset_index(drop=True)

    equity_curve = _build_equity_curve(working_daily, trades)
    return BacktestResult(trades=trades, equity_curve=equity_curve)
