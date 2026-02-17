from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Template

from limitup_lab.backtest import run_backtest
from limitup_lab.fill_models import FillModel
from limitup_lab.labels import label_one_word, label_sealed
from limitup_lab.returns import add_next_day_returns
from limitup_lab.stats import group_stats
from limitup_lab.streaks import compute_limitup_streak, exclude_suspended, exclude_unlimited_days
from limitup_lab.strategies import BuyFirstLimitUpSellNextCloseStrategy

try:
    import plotly.graph_objects as go
    from plotly.offline import get_plotlyjs

    HAS_PLOTLY = True
except ImportError:  # pragma: no cover - runtime environment specific.
    HAS_PLOTLY = False
    go = None
    get_plotlyjs = None


@dataclass
class ReportArtifacts:
    html_path: Path
    asset_paths: list[Path]


@dataclass
class InteractiveChart:
    chart_id: str
    title: str
    description: str
    plotly_json: str
    fallback_png: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_template_path() -> Path:
    return _project_root() / "templates" / "report.html.j2"


def _default_stylesheet_path() -> Path:
    return _project_root() / "assets" / "report.css"


def _load_processed_data(processed_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_path = processed_dir / "daily.parquet"
    instruments_path = processed_dir / "instruments.parquet"
    if not daily_path.exists():
        raise ValueError(f"缺少输入文件: {daily_path}")
    if not instruments_path.exists():
        raise ValueError(f"缺少输入文件: {instruments_path}")

    daily_bars = pd.read_parquet(daily_path)
    instruments = pd.read_parquet(instruments_path)
    return daily_bars, instruments


def _prepare_dataset(daily_bars: pd.DataFrame, instruments: pd.DataFrame) -> pd.DataFrame:
    with_one_word = label_one_word(daily_bars, instruments)
    labeled_daily = label_sealed(with_one_word, instruments)
    filtered_daily = exclude_unlimited_days(labeled_daily, instruments_df=instruments)
    filtered_daily = exclude_suspended(filtered_daily)
    with_streak = compute_limitup_streak(filtered_daily)
    with_returns = add_next_day_returns(with_streak)

    instrument_tags = instruments.loc[:, ["ts_code", "board", "is_st"]].drop_duplicates(subset=["ts_code"])
    merged_dataset = with_returns.merge(instrument_tags, on="ts_code", how="left")
    merged_dataset["one_word"] = merged_dataset["label_one_word"]
    merged_dataset["opened"] = merged_dataset["label_opened"]
    return merged_dataset


def _max_drawdown(equity_curve: pd.DataFrame) -> float:
    if equity_curve.empty:
        return 0.0
    running_peak = equity_curve["equity"].cummax()
    drawdown = equity_curve["equity"] / running_peak - 1.0
    return float(drawdown.min())


def _premium_rows(dataset: pd.DataFrame) -> pd.DataFrame:
    if "label_limit_up" not in dataset.columns or "next_open_ret" not in dataset.columns:
        return pd.DataFrame(columns=dataset.columns)
    limit_up_flag = dataset["label_limit_up"].astype(bool)
    return dataset.loc[limit_up_flag & dataset["next_open_ret"].notna()].copy()


def _plotly_json_from_figure(figure: Any | None) -> str:
    if not HAS_PLOTLY or figure is None:
        return "{}"
    return figure.to_json()


def _build_streak_distribution_chart(dataset: pd.DataFrame, chart_path: Path, fallback_png: str) -> InteractiveChart:
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    if "label_limit_up" in dataset.columns and "streak_up" in dataset.columns:
        limit_up_rows = dataset.loc[dataset["label_limit_up"].astype(bool)]
        streak_counts = limit_up_rows.groupby("streak_up").size().sort_index()
    else:
        streak_counts = pd.Series(dtype=float)

    figure, axis = plt.subplots(figsize=(7, 4))
    if streak_counts.empty:
        axis.text(0.5, 0.5, "No streak data", ha="center", va="center")
        axis.set_axis_off()
    else:
        axis.bar([str(streak) for streak in streak_counts.index], streak_counts.values, color="#235f8b")
        axis.set_title("Streak Distribution (Limit-Up Days)")
        axis.set_xlabel("streak_up")
        axis.set_ylabel("count")
    figure.tight_layout()
    figure.savefig(chart_path, dpi=120)
    plt.close(figure)

    plotly_figure = None
    if HAS_PLOTLY:
        plotly_figure = go.Figure()
        if streak_counts.empty:
            plotly_figure.add_annotation(text="No streak data", x=0.5, y=0.5, showarrow=False)
        else:
            plotly_figure.add_trace(
                go.Bar(
                    x=[str(streak) for streak in streak_counts.index],
                    y=streak_counts.values.tolist(),
                    marker_color="#235f8b",
                    hovertemplate="streak=%{x}<br>count=%{y}<extra></extra>",
                )
            )
        plotly_figure.update_layout(
            template="plotly_white",
            title="连板分布（streak_up）",
            xaxis_title="streak_up",
            yaxis_title="count",
            margin=dict(l=40, r=20, t=50, b=40),
        )

    return InteractiveChart(
        chart_id="chart_streak_distribution",
        title="连板分布（streak_up）",
        description="统计涨停样本中各连板层级出现次数，用于判断生态集中度。",
        plotly_json=_plotly_json_from_figure(plotly_figure),
        fallback_png=fallback_png,
    )


def _build_premium_by_streak_chart(dataset: pd.DataFrame, chart_path: Path, fallback_png: str) -> InteractiveChart:
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    premium_rows = _premium_rows(dataset)
    streak_levels = sorted(premium_rows["streak_up"].dropna().unique().tolist()) if not premium_rows.empty else []

    figure, axis = plt.subplots(figsize=(7, 4))
    if not streak_levels:
        axis.text(0.5, 0.5, "No premium data", ha="center", va="center")
        axis.set_axis_off()
    else:
        grouped_values = [premium_rows.loc[premium_rows["streak_up"] == streak, "next_open_ret"] for streak in streak_levels]
        axis.boxplot(grouped_values, tick_labels=[str(streak) for streak in streak_levels], showfliers=False)
        axis.axhline(0, color="#555", linewidth=1)
        axis.set_title("Next-Day Premium by Streak")
        axis.set_xlabel("streak_up")
        axis.set_ylabel("next_open_ret")
    figure.tight_layout()
    figure.savefig(chart_path, dpi=120)
    plt.close(figure)

    plotly_figure = None
    if HAS_PLOTLY:
        plotly_figure = go.Figure()
        if not streak_levels:
            plotly_figure.add_annotation(text="No premium data", x=0.5, y=0.5, showarrow=False)
        else:
            for streak in streak_levels:
                streak_values = premium_rows.loc[premium_rows["streak_up"] == streak, "next_open_ret"]
                plotly_figure.add_trace(
                    go.Box(
                        y=streak_values.tolist(),
                        name=str(streak),
                        boxpoints=False,
                        hovertemplate="streak=%{x}<br>ret=%{y:.4f}<extra></extra>",
                    )
                )
        plotly_figure.update_layout(
            template="plotly_white",
            title="次日溢价分布（按 streak 分组）",
            xaxis_title="streak_up",
            yaxis_title="next_open_ret",
            margin=dict(l=40, r=20, t=50, b=40),
        )

    return InteractiveChart(
        chart_id="chart_premium_by_streak",
        title="次日溢价分布（按 streak 分组）",
        description="箱线图展示不同连板层级的次日开盘溢价分布差异。",
        plotly_json=_plotly_json_from_figure(plotly_figure),
        fallback_png=fallback_png,
    )


def _build_sealed_vs_nonsealed_chart(dataset: pd.DataFrame, chart_path: Path, fallback_png: str) -> InteractiveChart:
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    premium_rows = _premium_rows(dataset)
    if "label_sealed" in premium_rows.columns:
        sealed_flag = premium_rows["label_sealed"].astype(bool)
    else:
        sealed_flag = pd.Series(False, index=premium_rows.index)
    premium_rows["tradability_group"] = sealed_flag.map(lambda is_sealed: "Sealed" if bool(is_sealed) else "Non-Sealed")
    sealed_values = premium_rows.loc[premium_rows["tradability_group"] == "Sealed", "next_open_ret"]
    non_sealed_values = premium_rows.loc[premium_rows["tradability_group"] == "Non-Sealed", "next_open_ret"]

    figure, axis = plt.subplots(figsize=(7, 4))
    if sealed_values.empty and non_sealed_values.empty:
        axis.text(0.5, 0.5, "No tradability data", ha="center", va="center")
        axis.set_axis_off()
    else:
        box_data = []
        labels = []
        if not sealed_values.empty:
            box_data.append(sealed_values)
            labels.append("Sealed")
        if not non_sealed_values.empty:
            box_data.append(non_sealed_values)
            labels.append("Non-Sealed")
        axis.boxplot(box_data, tick_labels=labels, showfliers=False)
        axis.axhline(0, color="#555", linewidth=1)
        axis.set_title("Sealed vs Non-Sealed Premium")
        axis.set_ylabel("next_open_ret")
    figure.tight_layout()
    figure.savefig(chart_path, dpi=120)
    plt.close(figure)

    plotly_figure = None
    if HAS_PLOTLY:
        plotly_figure = go.Figure()
        if sealed_values.empty and non_sealed_values.empty:
            plotly_figure.add_annotation(text="No tradability data", x=0.5, y=0.5, showarrow=False)
        else:
            if not sealed_values.empty:
                plotly_figure.add_trace(
                    go.Box(
                        y=sealed_values.tolist(),
                        name="Sealed",
                        boxpoints=False,
                        marker_color="#ad2e24",
                        hovertemplate="group=Sealed<br>ret=%{y:.4f}<extra></extra>",
                    )
                )
            if not non_sealed_values.empty:
                plotly_figure.add_trace(
                    go.Box(
                        y=non_sealed_values.tolist(),
                        name="Non-Sealed",
                        boxpoints=False,
                        marker_color="#1f7a45",
                        hovertemplate="group=Non-Sealed<br>ret=%{y:.4f}<extra></extra>",
                    )
                )
        plotly_figure.update_layout(
            template="plotly_white",
            title="封死 / 非封死 次日溢价对比",
            yaxis_title="next_open_ret",
            margin=dict(l=40, r=20, t=50, b=40),
        )

    return InteractiveChart(
        chart_id="chart_sealed_nonsealed",
        title="封死 / 非封死 次日溢价对比",
        description="比较可交易性差异对次日溢价分布的影响。",
        plotly_json=_plotly_json_from_figure(plotly_figure),
        fallback_png=fallback_png,
    )


def _build_sensitivity_compare_chart(
    compare_rows: list[dict[str, Any]],
    chart_path: Path,
    fallback_png: str,
) -> InteractiveChart:
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    models = [str(row["fill_model"]) for row in compare_rows]
    total_returns = [float(row["total_return"]) for row in compare_rows]
    max_drawdowns = [float(row["max_drawdown"]) for row in compare_rows]

    figure, axis = plt.subplots(figsize=(7, 4))
    if not models:
        axis.text(0.5, 0.5, "No sensitivity data", ha="center", va="center")
        axis.set_axis_off()
    else:
        positions = list(range(len(models)))
        bar_width = 0.38
        axis.bar(
            [position - bar_width / 2 for position in positions],
            total_returns,
            width=bar_width,
            label="total_return",
        )
        axis.bar(
            [position + bar_width / 2 for position in positions],
            max_drawdowns,
            width=bar_width,
            label="max_drawdown",
        )
        axis.set_xticks(positions, models)
        axis.axhline(0, color="#555", linewidth=1)
        axis.set_title("IDEAL vs CONS: Return & Drawdown")
        axis.set_ylabel("ratio")
        axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(chart_path, dpi=120)
    plt.close(figure)

    plotly_figure = None
    if HAS_PLOTLY:
        plotly_figure = go.Figure()
        if not models:
            plotly_figure.add_annotation(text="No sensitivity data", x=0.5, y=0.5, showarrow=False)
        else:
            plotly_figure.add_trace(
                go.Bar(
                    x=models,
                    y=total_returns,
                    name="total_return",
                    marker_color="#235f8b",
                    hovertemplate="model=%{x}<br>total_return=%{y:.4f}<extra></extra>",
                )
            )
            plotly_figure.add_trace(
                go.Bar(
                    x=models,
                    y=max_drawdowns,
                    name="max_drawdown",
                    marker_color="#ad2e24",
                    hovertemplate="model=%{x}<br>max_drawdown=%{y:.4f}<extra></extra>",
                )
            )
        plotly_figure.update_layout(
            template="plotly_white",
            barmode="group",
            title="IDEAL vs CONS 收益/回撤对比",
            xaxis_title="fill_model",
            yaxis_title="ratio",
            margin=dict(l=40, r=20, t=50, b=40),
        )

    return InteractiveChart(
        chart_id="chart_sensitivity_compare",
        title="IDEAL vs CONS 收益/回撤对比",
        description="条形图比较两种成交假设下的总收益与最大回撤。",
        plotly_json=_plotly_json_from_figure(plotly_figure),
        fallback_png=fallback_png,
    )


def _format_group_rows(grouped_stats: pd.DataFrame) -> list[dict[str, Any]]:
    if grouped_stats.empty:
        return []

    rows: list[dict[str, Any]] = []
    for row in grouped_stats.to_dict(orient="records"):
        rows.append(
            {
                "streak_up": int(row["streak_up"]),
                "one_word": bool(row["one_word"]),
                "opened": bool(row["opened"]),
                "count": int(row["count"]),
                "next_open_ret_p10": float(row["next_open_ret_p10"]),
                "next_open_ret_p50": float(row["next_open_ret_p50"]),
                "next_open_ret_p90": float(row["next_open_ret_p90"]),
                "next_close_ret_p10": float(row["next_close_ret_p10"]),
                "next_close_ret_p50": float(row["next_close_ret_p50"]),
                "next_close_ret_p90": float(row["next_close_ret_p90"]),
            }
        )
    return rows


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _format_trade_date(value: object) -> str:
    parsed = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(parsed):
        return "-"
    return parsed.strftime("%Y-%m-%d")


def _build_kpi_metrics(dataset: pd.DataFrame, compare_rows: list[dict[str, Any]]) -> dict[str, float | int | str]:
    sample_count = int(len(dataset))
    limit_up_mask = dataset["label_limit_up"] if "label_limit_up" in dataset.columns else pd.Series(False, index=dataset.index)
    limit_up_count = int(limit_up_mask.sum())

    sealed_count = int((dataset.get("label_sealed", pd.Series(False, index=dataset.index)) & limit_up_mask).sum())
    one_word_count = int((dataset.get("label_one_word", pd.Series(False, index=dataset.index)) & limit_up_mask).sum())

    next_open_median = float(
        dataset.loc[limit_up_mask & dataset["next_open_ret"].notna(), "next_open_ret"].median()
    ) if sample_count else 0.0
    if pd.isna(next_open_median):
        next_open_median = 0.0

    compare_map = {str(row["fill_model"]): row for row in compare_rows}
    ideal_total_return = float(compare_map.get("IDEAL", {}).get("total_return", 0.0))
    conservative_total_return = float(compare_map.get("CONSERVATIVE", {}).get("total_return", 0.0))

    if sample_count == 0:
        start_date = "-"
        end_date = "-"
    else:
        start_date = _format_trade_date(dataset["trade_date"].min())
        end_date = _format_trade_date(dataset["trade_date"].max())

    return {
        "sample_count": sample_count,
        "limit_up_count": limit_up_count,
        "sealed_ratio": _safe_ratio(sealed_count, limit_up_count),
        "one_word_ratio": _safe_ratio(one_word_count, limit_up_count),
        "next_day_premium_median": next_open_median,
        "ideal_cons_gap": ideal_total_return - conservative_total_return,
        "start_date": start_date,
        "end_date": end_date,
    }


def _build_executive_summary(kpi_metrics: dict[str, float | int | str]) -> str:
    limit_up_count = int(kpi_metrics["limit_up_count"])
    if limit_up_count == 0:
        return "样本期内未出现可识别涨停样本，当前数据不足以支持涨停生态结论。"

    sealed_ratio = float(kpi_metrics["sealed_ratio"]) * 100
    one_word_ratio = float(kpi_metrics["one_word_ratio"]) * 100
    premium_median = float(kpi_metrics["next_day_premium_median"]) * 100
    ideal_cons_gap = float(kpi_metrics["ideal_cons_gap"]) * 100

    return (
        f"样本区间共识别 {limit_up_count} 条涨停样本，封死比例 {sealed_ratio:.1f}% 、一字板比例 {one_word_ratio:.1f}% ，"
        f"次日开盘溢价中位数 {premium_median:.2f}% 。同一策略在 IDEAL 与 CONSERVATIVE 假设下收益差 {ideal_cons_gap:.2f}% ，"
        "说明成交假设会显著影响回测结论。"
    )


def _build_strategy_compare(dataset: pd.DataFrame) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    strategy = BuyFirstLimitUpSellNextCloseStrategy()
    ideal_result = run_backtest(dataset, strategy, fill_model=FillModel.IDEAL, fee_bps=0.0, slippage_bps=0.0)
    conservative_result = run_backtest(
        dataset,
        strategy,
        fill_model=FillModel.CONSERVATIVE,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    def summarize(label: str, trades: pd.DataFrame, equity: pd.DataFrame) -> dict[str, Any]:
        final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else 1.0
        total_return = final_equity - 1.0
        max_dd = _max_drawdown(equity)
        win_rate = float((trades["ret_net"] > 0).mean()) if not trades.empty else 0.0
        return {
            "fill_model": label,
            "trade_count": int(len(trades)),
            "total_return": total_return,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
        }

    compare_rows = [
        summarize("IDEAL", ideal_result.trades, ideal_result.equity_curve),
        summarize("CONSERVATIVE", conservative_result.trades, conservative_result.equity_curve),
    ]
    trade_columns = [
        "strategy_name",
        "fill_model",
        "ts_code",
        "entry_date",
        "entry_price",
        "exit_date",
        "exit_price",
        "ret_net",
    ]
    ideal_trades = ideal_result.trades.copy()
    conservative_trades = conservative_result.trades.copy()
    for dataframe in [ideal_trades, conservative_trades]:
        if dataframe.empty:
            for column_name in trade_columns:
                if column_name not in dataframe.columns:
                    dataframe[column_name] = pd.Series(dtype="object")
        dataframe["ret_pct"] = pd.to_numeric(dataframe["ret_net"], errors="coerce") * 100

    combined_trades = pd.concat([ideal_trades, conservative_trades], ignore_index=True)
    if not combined_trades.empty:
        combined_trades = combined_trades.sort_values(["entry_date", "ts_code", "fill_model"]).reset_index(
            drop=True
        )
    return compare_rows, combined_trades


def _format_trades_rows(trades: pd.DataFrame) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    rows: list[dict[str, Any]] = []
    for record in trades.to_dict(orient="records"):
        rows.append(
            {
                "strategy_name": str(record.get("strategy_name", "")),
                "fill_model": str(record.get("fill_model", "")),
                "ts_code": str(record.get("ts_code", "")),
                "entry_date": str(record.get("entry_date", "")),
                "entry_price": float(record.get("entry_price", 0.0)),
                "exit_date": str(record.get("exit_date", "")),
                "exit_price": float(record.get("exit_price", 0.0)),
                "ret_net": float(record.get("ret_net", 0.0)),
                "ret_pct": float(record.get("ret_pct", 0.0)),
            }
        )
    return rows


def generate_html_report(
    processed_dir: Path,
    out_dir: Path,
    template_path: Path | None = None,
) -> ReportArtifacts:
    daily_bars, instruments = _load_processed_data(processed_dir)
    dataset = _prepare_dataset(daily_bars, instruments)

    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    stylesheet_source = _default_stylesheet_path()
    if not stylesheet_source.exists():
        raise ValueError(f"样式文件不存在: {stylesheet_source}")
    stylesheet_target = assets_dir / "report.css"
    shutil.copy2(stylesheet_source, stylesheet_target)
    plotly_js_target: Path | None = None
    if HAS_PLOTLY and get_plotlyjs is not None:
        plotly_js_target = assets_dir / "plotly.min.js"
        plotly_js_target.write_text(get_plotlyjs(), encoding="utf-8")

    grouped_stats = group_stats(dataset, by=["streak_up", "one_word", "opened"])
    group_rows = _format_group_rows(grouped_stats)

    streak_chart_path = assets_dir / "streak_next_close_p50.png"
    premium_by_streak_chart_path = assets_dir / "next_open_ret_hist.png"
    sealed_nonsealed_chart_path = assets_dir / "sealed_vs_nonsealed_premium.png"
    equity_chart_path = assets_dir / "equity_compare.png"

    compare_rows, compare_trades = _build_strategy_compare(dataset)
    streak_chart = _build_streak_distribution_chart(
        dataset,
        streak_chart_path,
        str(streak_chart_path.relative_to(out_dir)),
    )
    premium_by_streak_chart = _build_premium_by_streak_chart(
        dataset,
        premium_by_streak_chart_path,
        str(premium_by_streak_chart_path.relative_to(out_dir)),
    )
    sealed_nonsealed_chart = _build_sealed_vs_nonsealed_chart(
        dataset,
        sealed_nonsealed_chart_path,
        str(sealed_nonsealed_chart_path.relative_to(out_dir)),
    )
    sensitivity_chart = _build_sensitivity_compare_chart(
        compare_rows,
        equity_chart_path,
        str(equity_chart_path.relative_to(out_dir)),
    )
    kpi_metrics = _build_kpi_metrics(dataset, compare_rows)
    executive_summary = _build_executive_summary(kpi_metrics)
    trades_rows = _format_trades_rows(compare_trades)

    tables_dir = out_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    group_csv_path = tables_dir / "group_quantiles.csv"
    trades_csv_path = tables_dir / "trades.csv"
    compare_csv_path = tables_dir / "strategy_compare.csv"
    grouped_stats.to_csv(group_csv_path, index=False)
    compare_trades.to_csv(trades_csv_path, index=False)
    pd.DataFrame(compare_rows).to_csv(compare_csv_path, index=False)

    selected_template_path = template_path or _default_template_path()
    if not selected_template_path.exists():
        raise ValueError(f"模板文件不存在: {selected_template_path}")

    template = Template(selected_template_path.read_text(encoding="utf-8"))
    html_content = template.render(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data_start=str(kpi_metrics["start_date"]),
        data_end=str(kpi_metrics["end_date"]),
        executive_summary=executive_summary,
        disclaimer=(
            "本报告为研究与策略体检用途，不构成投资建议；日频标签为近似定义，无法还原盘中成交细节。"
        ),
        kpi_metrics=kpi_metrics,
        total_rows=int(len(dataset)),
        limit_up_rows=int(dataset["label_limit_up"].sum()) if "label_limit_up" in dataset else 0,
        group_rows=group_rows,
        compare_rows=compare_rows,
        trades_rows=trades_rows,
        stylesheet_path=str(stylesheet_target.relative_to(out_dir)),
        plotly_js_path=str(plotly_js_target.relative_to(out_dir)) if plotly_js_target else None,
        has_plotly=HAS_PLOTLY and plotly_js_target is not None,
        csv_paths={
            "group_quantiles": str(group_csv_path.relative_to(out_dir)),
            "trades": str(trades_csv_path.relative_to(out_dir)),
            "strategy_compare": str(compare_csv_path.relative_to(out_dir)),
        },
        charts={
            "streak_distribution": streak_chart,
            "premium_by_streak": premium_by_streak_chart,
            "sealed_nonsealed": sealed_nonsealed_chart,
            "sensitivity_compare": sensitivity_chart,
        },
    )

    index_path = out_dir / "index.html"
    report_path = out_dir / "report.html"
    index_path.write_text(html_content, encoding="utf-8")
    report_path.write_text(html_content, encoding="utf-8")
    asset_paths = [
        stylesheet_target,
        streak_chart_path,
        premium_by_streak_chart_path,
        sealed_nonsealed_chart_path,
        equity_chart_path,
        group_csv_path,
        trades_csv_path,
        compare_csv_path,
    ]
    if plotly_js_target is not None:
        asset_paths.append(plotly_js_target)

    return ReportArtifacts(html_path=index_path, asset_paths=asset_paths)
