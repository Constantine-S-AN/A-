from __future__ import annotations

import json
from pathlib import Path
import shutil
import zipfile

import numpy as np
import pandas as pd
import typer

from limitup_lab.adapters import fetch_akshare_dataset
from limitup_lab.io import read_daily_bars, read_instruments, write_parquet
from limitup_lab.report import generate_html_report

app = typer.Typer(
    help="A股涨停板生态研究与策略体检（Phase 1，日频）",
    no_args_is_help=True,
)


def _ensure_parent_directory(file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)


def _read_csv_or_fail(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        raise typer.BadParameter(f"输入文件不存在: {file_path}")
    try:
        return pd.read_csv(file_path)
    except Exception as exc:  # pragma: no cover - pandas message varies by version.
        raise typer.BadParameter(f"无法读取 CSV 文件: {file_path}") from exc


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_demo_fixture_paths(project_root: Path) -> tuple[Path, Path]:
    fixture_dir = project_root / "tests" / "fixtures"
    preferred_daily = fixture_dir / "demo_daily_bars.csv"
    preferred_instruments = fixture_dir / "demo_instruments.csv"
    if preferred_daily.exists() and preferred_instruments.exists():
        return preferred_daily, preferred_instruments
    return fixture_dir / "daily_bars.csv", fixture_dir / "instruments.csv"


def _parse_symbols(symbols_text: str) -> list[str]:
    symbol_list = [symbol.strip().upper() for symbol in symbols_text.split(",")]
    return [symbol for symbol in symbol_list if symbol]


def _read_json_if_exists(file_path: Path) -> dict[str, float | int]:
    if not file_path.exists():
        return {}
    try:
        loaded_data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(loaded_data, dict):
        return loaded_data
    return {}


def _read_csv_if_exists(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(file_path)
    except Exception:
        return pd.DataFrame()


def _weighted_average(values: pd.Series, weights: pd.Series) -> float:
    if values.empty or weights.empty:
        return 0.0
    weight_sum = float(weights.sum())
    if np.isclose(weight_sum, 0.0):
        return 0.0
    return float(np.average(values, weights=weights))


def _build_backtest_illusion_chart(chart_path: Path) -> tuple[float, float]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return 0.22, -0.15

    event_index = np.arange(1, 6)
    ideal_equity = np.array([1.00, 1.05, 1.11, 1.17, 1.22], dtype=float)
    conservative_equity = np.array([1.00, 0.97, 0.93, 0.89, 0.85], dtype=float)

    figure, axis = plt.subplots(figsize=(8, 4.6))
    axis.plot(event_index, ideal_equity, marker="o", linewidth=2.2, label="IDEAL")
    axis.plot(
        event_index,
        conservative_equity,
        marker="o",
        linewidth=2.2,
        label="CONSERVATIVE",
    )
    axis.set_title("Backtest Illusion Example")
    axis.set_xlabel("Event")
    axis.set_ylabel("Equity")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(chart_path, dpi=120)
    plt.close(figure)

    return float(ideal_equity[-1] - 1.0), float(conservative_equity[-1] - 1.0)


def _zip_directory(source_dir: Path, zip_path: Path) -> Path:
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"目录不存在: {source_dir}")
    _ensure_parent_directory(zip_path)
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(source_dir.rglob("*")):
            if not file_path.is_file():
                continue
            archive.write(file_path, arcname=file_path.relative_to(source_dir))
    return zip_path


def _export_pdf_with_playwright(html_path: Path, pdf_path: Path) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright 未安装，跳过 PDF 导出。"

    _ensure_parent_directory(pdf_path)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
                page.pdf(path=str(pdf_path), format="A4", print_background=True)
            finally:
                browser.close()
    except Exception as exc:  # pragma: no cover - depends on runtime browser availability.
        return False, f"Playwright 导出失败: {exc}"

    return True, f"Wrote PDF to {pdf_path}"


def _export_report_downloads(
    html_path: Path,
    pdf_path: Path,
    zip_fallback_path: Path | None,
) -> tuple[bool, str, Path | None]:
    report_root = html_path.parent
    zipped_bundle_path: Path | None = None
    if zip_fallback_path is not None:
        zipped_bundle_path = _zip_directory(report_root, zip_fallback_path)

    pdf_created, pdf_message = _export_pdf_with_playwright(html_path, pdf_path)
    return pdf_created, pdf_message, zipped_bundle_path


def _build_site_landing(site_dir: Path, demo_report_dir: Path | None) -> Path:
    assets_dir = site_dir / "assets"
    images_dir = assets_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    source_css = _project_root() / "assets" / "report.css"
    if source_css.exists():
        shutil.copy2(source_css, assets_dir / "report.css")

    thumbnail_specs = [
        ("连板分布", "streak_next_close_p50.png"),
        ("封死/非封死对比", "sealed_vs_nonsealed_premium.png"),
        ("成交假设敏感性", "equity_compare.png"),
    ]
    thumbnails: list[dict[str, str]] = []
    if demo_report_dir is not None:
        for title, filename in thumbnail_specs:
            source_image = demo_report_dir / "assets" / filename
            if not source_image.exists():
                continue
            target_image = images_dir / filename
            shutil.copy2(source_image, target_image)
            thumbnails.append({"title": title, "path": f"assets/images/{filename}"})

    summary_path = demo_report_dir / "summary.json" if demo_report_dir is not None else None
    summary: dict[str, float | int] = {}
    if summary_path is not None and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    if summary:
        sample_count = int(summary.get("total_rows", 0))
        limit_up_count = int(summary.get("limit_up_days", 0))
        limit_up_rate = float(summary.get("limit_up_rate", 0.0)) * 100
        blocked_count = int(summary.get("blocked_buy_days_conservative", 0))
        one_line_conclusion = (
            f"Demo 样本共 {sample_count} 条，涨停 {limit_up_count} 条（{limit_up_rate:.2f}%），"
            f"保守成交下有 {blocked_count} 条无法买入，成交假设会明显改变回测结论。"
        )
    else:
        one_line_conclusion = "请先构建 demo 报告后查看策略体检结论。"

    if demo_report_dir is not None and (demo_report_dir / "index.html").exists():
        demo_link = "reports/demo/index.html"
    else:
        demo_link = "#"

    download_links: list[str] = []
    if (site_dir / "demo.pdf").exists():
        download_links.append('<a class="cta-link" href="demo.pdf">下载 Demo PDF</a>')
    if (site_dir / "demo-html.zip").exists():
        download_links.append('<a class="cta-link" href="demo-html.zip">下载 Demo HTML ZIP</a>')

    download_html = (
        "<p>" + " | ".join(download_links) + "</p>"
        if download_links
        else "<p>暂未生成可下载报告文件。</p>"
    )

    thumbnail_html = "\n".join(
        [
            (
                f'      <article class="thumb-card">'
                f'<a href="{item["path"]}" target="_blank"><img src="{item["path"]}" alt="{item["title"]}" /></a>'
                f'<p>{item["title"]}</p>'
                f"</article>"
            )
            for item in thumbnails
        ]
    )

    landing_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LimitUp Lab Site</title>
  <link rel="stylesheet" href="assets/report.css" />
  <style>
    .landing {{ margin-top: 18px; }}
    .landing section {{ margin-top: 18px; }}
    .thumb-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      margin-top: 10px;
    }}
    .thumb-card {{
      border: 1px solid #dbe1ea;
      border-radius: 10px;
      background: #fff;
      padding: 10px;
    }}
    .thumb-card img {{
      width: 100%;
      display: block;
      border-radius: 8px;
    }}
    .thumb-card p {{ margin: 8px 0 0; }}
    .cta-link {{ font-weight: 700; }}
  </style>
</head>
<body>
  <main class="report-shell landing">
    <header class="report-header">
      <h1 class="report-title">LimitUp Lab Pages Site</h1>
      <p class="report-subtitle">A 股涨停板生态研究与策略体检（Phase 1, 日频）</p>
      <p class="report-subtitle">一句话结论：{one_line_conclusion}</p>
    </header>

    <section class="section">
      <h2>项目介绍</h2>
      <p>本站为静态产物，可直接托管到 Pages。核心内容是 demo 报告归档与关键图概览。</p>
      <p><a class="cta-link" href="{demo_link}">打开 Demo 报告</a></p>
      <p><a class="cta-link" href="case-study.html">打开 Case Study</a></p>
      {download_html}
    </section>

    <section class="section">
      <h2>关键图缩略图</h2>
      <div class="thumb-grid">
{thumbnail_html if thumbnail_html else '        <p>暂无缩略图，请先使用 --demo 构建报告。</p>'}
      </div>
    </section>
  </main>
</body>
</html>
"""

    landing_path = site_dir / "index.html"
    landing_path.write_text(landing_html, encoding="utf-8")
    return landing_path


def _build_case_study_page(site_dir: Path, demo_report_dir: Path | None) -> Path:
    assets_dir = site_dir / "assets"
    images_dir = assets_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    conclusion_chart_specs = [
        ("streak_next_close_p50.png", "ecosystem_streak.png"),
        ("next_open_ret_hist.png", "premium_by_streak.png"),
        ("sealed_vs_nonsealed_premium.png", "tradability_gap.png"),
        ("equity_compare.png", "sensitivity_compare.png"),
    ]
    copied_charts: dict[str, str] = {}
    if demo_report_dir is not None:
        for source_name, target_name in conclusion_chart_specs:
            source_path = demo_report_dir / "assets" / source_name
            if not source_path.exists():
                continue
            target_path = images_dir / target_name
            shutil.copy2(source_path, target_path)
            copied_charts[target_name] = f"assets/images/{target_name}"

    summary = (
        _read_json_if_exists(demo_report_dir / "summary.json")
        if demo_report_dir is not None
        else {}
    )
    group_quantiles = (
        _read_csv_if_exists(demo_report_dir / "tables" / "group_quantiles.csv")
        if demo_report_dir is not None
        else pd.DataFrame()
    )
    strategy_compare = (
        _read_csv_if_exists(demo_report_dir / "tables" / "strategy_compare.csv")
        if demo_report_dir is not None
        else pd.DataFrame()
    )

    sample_count = int(summary.get("total_rows", 0))
    limit_up_count = int(summary.get("limit_up_days", 0))
    limit_up_rate_pct = float(summary.get("limit_up_rate", 0.0)) * 100
    blocked_ratio_pct = float(summary.get("blocked_buy_ratio_conservative", 0.0)) * 100

    streak_statement = (
        "结论 1：涨停生态样本规模有限。"
        f" 当前 demo 样本 {sample_count} 条，涨停 {limit_up_count} 条，涨停占比 {limit_up_rate_pct:.2f}%。"
    )
    premium_statement = "结论 2：次日溢价分布与连板层级相关，需按分组观察而非看整体均值。"
    tradability_statement = (
        "结论 3：可交易性限制不可忽略。"
        f" 在保守成交假设下，无法买入占比约 {blocked_ratio_pct:.2f}%。"
    )

    if not group_quantiles.empty:
        normalized_group = group_quantiles.copy()
        normalized_group["streak_up"] = pd.to_numeric(
            normalized_group.get("streak_up"), errors="coerce"
        )
        normalized_group["count"] = pd.to_numeric(normalized_group.get("count"), errors="coerce")
        normalized_group["next_open_ret_p50"] = pd.to_numeric(
            normalized_group.get("next_open_ret_p50"), errors="coerce"
        )
        normalized_group["next_close_ret_p50"] = pd.to_numeric(
            normalized_group.get("next_close_ret_p50"), errors="coerce"
        )

        low_streak_rows = normalized_group.loc[normalized_group["streak_up"] <= 1]
        high_streak_rows = normalized_group.loc[normalized_group["streak_up"] >= 2]
        if not low_streak_rows.empty and not high_streak_rows.empty:
            low_median = _weighted_average(
                low_streak_rows["next_open_ret_p50"], low_streak_rows["count"]
            )
            high_median = _weighted_average(
                high_streak_rows["next_open_ret_p50"], high_streak_rows["count"]
            )
            premium_statement = (
                "结论 2：连板层级提升后，次日开盘溢价中位数出现分层。"
                f" streak<=1 约 {low_median * 100:.2f}%，streak>=2 约 {high_median * 100:.2f}%。"
            )

        opened_bool = (
            normalized_group.get("opened")
            .astype("string")
            .str.strip()
            .str.lower()
            .isin(["1", "true", "yes"])
        )
        opened_rows = normalized_group.loc[opened_bool]
        non_opened_rows = normalized_group.loc[~opened_bool]
        if not opened_rows.empty and not non_opened_rows.empty:
            opened_median = _weighted_average(
                opened_rows["next_close_ret_p50"], opened_rows["count"]
            )
            non_opened_median = _weighted_average(
                non_opened_rows["next_close_ret_p50"], non_opened_rows["count"]
            )
            tradability_statement = (
                "结论 3：开板与否会改变次日收盘表现。"
                f" opened 样本中位数 {opened_median * 100:.2f}%，"
                f" non-opened 样本中位数 {non_opened_median * 100:.2f}%。"
            )

    ideal_return = 0.0
    conservative_return = 0.0
    if not strategy_compare.empty and "fill_model" in strategy_compare.columns:
        compared = strategy_compare.copy()
        compared["fill_model_norm"] = compared["fill_model"].astype("string").str.upper()
        compared["total_return"] = pd.to_numeric(compared.get("total_return"), errors="coerce")
        ideal_rows = compared.loc[compared["fill_model_norm"] == "IDEAL", "total_return"]
        conservative_rows = compared.loc[
            compared["fill_model_norm"] == "CONSERVATIVE", "total_return"
        ]
        if not ideal_rows.empty and not conservative_rows.empty:
            ideal_return = float(ideal_rows.iloc[0])
            conservative_return = float(conservative_rows.iloc[0])

    illusion_chart_path = images_dir / "backtest_illusion_example.png"
    example_ideal_return, example_conservative_return = _build_backtest_illusion_chart(
        illusion_chart_path
    )
    example_gap = example_ideal_return - example_conservative_return

    demo_result_note = (
        f"当前 demo 实测（真实输出）：IDEAL {ideal_return * 100:.2f}%，"
        f" CONSERVATIVE {conservative_return * 100:.2f}%。"
    )

    demo_report_link = "reports/demo/index.html"
    case_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LimitUp Lab Case Study</title>
  <link rel="stylesheet" href="assets/report.css" />
  <style>
    .case-shell {{ max-width: 1060px; margin: 0 auto; padding: 22px; }}
    .hero {{ margin-top: 10px; }}
    .hero p {{ margin: 6px 0; }}
    .conclusion-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
    }}
    .conclusion-card {{
      border: 1px solid #dbe1ea;
      border-radius: 10px;
      background: #fff;
      padding: 12px;
    }}
    .conclusion-card img {{
      width: 100%;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      margin-top: 8px;
    }}
    .section {{ margin-top: 20px; }}
  </style>
</head>
<body>
  <main class="case-shell">
    <header class="hero">
      <h1>Case Study：涨停板生态与可成交性</h1>
      <p>这是一份可独立阅读的小研报，复用 demo 输出并补充一个“回测幻觉”机制示例。</p>
      <p><a href="index.html">返回站点首页</a> | <a href="{demo_report_link}">打开完整 Demo 报告</a></p>
    </header>

    <section class="section">
      <h2>三个可复现结论</h2>
      <div class="conclusion-grid">
        <article class="conclusion-card">
          <h3>结论 1：生态样本与连板结构</h3>
          <p>{streak_statement}</p>
          <img src="{copied_charts.get('ecosystem_streak.png', 'assets/images/streak_next_close_p50.png')}" alt="streak chart" />
        </article>
        <article class="conclusion-card">
          <h3>结论 2：次日溢价分层</h3>
          <p>{premium_statement}</p>
          <img src="{copied_charts.get('premium_by_streak.png', 'assets/images/next_open_ret_hist.png')}" alt="premium by streak chart" />
        </article>
        <article class="conclusion-card">
          <h3>结论 3：可交易性约束</h3>
          <p>{tradability_statement}</p>
          <img src="{copied_charts.get('tradability_gap.png', 'assets/images/sealed_vs_nonsealed_premium.png')}" alt="tradability gap chart" />
        </article>
      </div>
    </section>

    <section class="section">
      <h2>回测幻觉示例：IDEAL 赚钱，CONSERVATIVE 崩掉</h2>
      <p>
        机制示例（固定样例，可复现）：IDEAL 总收益 {example_ideal_return * 100:.2f}%；
        CONSERVATIVE 总收益 {example_conservative_return * 100:.2f}%；
        差值 {example_gap * 100:.2f}%。
      </p>
      <p>{demo_result_note}</p>
      <img src="assets/images/backtest_illusion_example.png" alt="backtest illusion example" />
    </section>

    <section class="section">
      <h2>假设与边界</h2>
      <p>
        本页面基于日频近似，未接入分钟线与 L2 数据。封单质量、盘中回封节奏、临停扰动均未显式建模，
        结论用于研究与体检，不代表实盘可直接复现。
      </p>
    </section>
  </main>
</body>
</html>
"""

    case_study_path = site_dir / "case-study.html"
    case_study_path.write_text(case_html, encoding="utf-8")
    return case_study_path


@app.command("ingest")
def ingest(
    daily_path: Path = typer.Option(
        ...,
        "--daily",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="日线数据文件（CSV 或 Parquet）",
    ),
    instruments_path: Path = typer.Option(
        ...,
        "--instruments",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="标的信息文件（CSV 或 Parquet）",
    ),
    out_dir: Path = typer.Option(
        Path("data/processed"),
        "--out",
        "-o",
        help="输出目录（写出 daily.parquet 和 instruments.parquet）",
    ),
) -> None:
    """Read daily/instruments files and write canonical parquet outputs."""
    try:
        canonical_daily_bars = read_daily_bars(daily_path)
        canonical_instruments = read_instruments(instruments_path)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    daily_output_path = out_dir / "daily.parquet"
    instruments_output_path = out_dir / "instruments.parquet"

    try:
        write_parquet(canonical_daily_bars, daily_output_path)
        write_parquet(canonical_instruments, instruments_output_path)
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Wrote canonical daily bars to {daily_output_path}")
    typer.echo(f"Wrote canonical instruments to {instruments_output_path}")


@app.command("fetch-akshare")
def fetch_akshare(
    symbols: str = typer.Option(
        ...,
        "--symbols",
        help="逗号分隔 ts_code 列表，例如: 002261.SZ,603598.SH,000957.SZ",
    ),
    start_date: str = typer.Option(
        ...,
        "--start",
        help="开始日期 YYYYMMDD，例如 20240101",
    ),
    end_date: str = typer.Option(
        ...,
        "--end",
        help="结束日期 YYYYMMDD，例如 20240630",
    ),
    out_dir: Path = typer.Option(
        Path("data/processed/real"),
        "--out",
        "-o",
        help="输出目录（写出 daily.parquet 和 instruments.parquet）",
    ),
    adjust: str = typer.Option(
        "",
        "--adjust",
        help="复权方式：空字符串不复权，或 qfq / hfq",
    ),
    with_names: bool = typer.Option(
        False,
        "--with-names/--without-names",
        help="是否拉取名称并推断 ST（会额外请求全市场快照，默认关闭以加速）",
    ),
) -> None:
    """Fetch real A-share daily bars from AkShare and write canonical parquet outputs."""
    symbol_list = _parse_symbols(symbols)
    try:
        daily_bars, instruments = fetch_akshare_dataset(
            ts_codes=symbol_list,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            include_names=with_names,
        )
    except (RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    daily_output_path = out_dir / "daily.parquet"
    instruments_output_path = out_dir / "instruments.parquet"
    try:
        write_parquet(daily_bars, daily_output_path)
        write_parquet(instruments, instruments_output_path)
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Wrote canonical daily bars to {daily_output_path}")
    typer.echo(f"Wrote canonical instruments to {instruments_output_path}")


@app.command("label")
def label(
    input_csv: Path = typer.Option(
        Path("data/ingested/daily_bars.csv"), "--input", "-i", help="标准化日线 CSV"
    ),
    output_csv: Path = typer.Option(
        Path("data/processed/limitup_labels.csv"),
        "--output",
        "-o",
        help="涨停生态标签 CSV",
    ),
    limit_ratio: float = typer.Option(0.10, "--limit-ratio", help="默认主板涨停比例"),
) -> None:
    """Generate limit-up labels and fill assumptions."""
    bars = _read_csv_or_fail(input_csv)
    bars = bars.rename(columns={"ts_code": "symbol", "vol": "volume"})
    required_columns = ["trade_date", "symbol", "open", "high", "low", "close", "volume"]
    missing_columns = [column for column in required_columns if column not in bars.columns]
    if missing_columns:
        raise typer.BadParameter(f"缺失必要列: {missing_columns}")

    labeled_bars = bars.copy()
    trade_date_text = labeled_bars["trade_date"].astype("string").str.strip()
    parsed_trade_dates = pd.to_datetime(trade_date_text, format="%Y%m%d", errors="coerce")
    fallback_mask = parsed_trade_dates.isna()
    if fallback_mask.any():
        parsed_trade_dates.loc[fallback_mask] = pd.to_datetime(
            trade_date_text.loc[fallback_mask], errors="coerce"
        )
    if parsed_trade_dates.isna().any():
        invalid_examples = trade_date_text[parsed_trade_dates.isna()].head(3).tolist()
        raise typer.BadParameter(f"trade_date 存在无法解析的值: {invalid_examples}")
    labeled_bars["trade_date"] = parsed_trade_dates.dt.strftime("%Y-%m-%d")
    labeled_bars = labeled_bars.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    labeled_bars["prev_close"] = labeled_bars.groupby("symbol")["close"].shift(1)
    labeled_bars["limit_price"] = (labeled_bars["prev_close"] * (1.0 + limit_ratio)).round(2)
    labeled_bars["is_limit_up"] = labeled_bars["limit_price"].notna() & (
        labeled_bars["high"] >= labeled_bars["limit_price"] - 1e-12
    )
    labeled_bars["close_at_limit"] = labeled_bars["limit_price"].notna() & np.isclose(
        labeled_bars["close"], labeled_bars["limit_price"], atol=0.01
    )
    labeled_bars["is_sealed_limit"] = labeled_bars["is_limit_up"] & labeled_bars["close_at_limit"]
    labeled_bars["can_buy_ideal"] = labeled_bars["is_limit_up"]
    labeled_bars["can_buy_conservative"] = ~labeled_bars["is_sealed_limit"]

    _ensure_parent_directory(output_csv)
    labeled_bars.to_csv(output_csv, index=False)
    typer.echo(f"Wrote labels to {output_csv}")


@app.command("stats")
def stats(
    input_csv: Path = typer.Option(
        Path("data/processed/limitup_labels.csv"), "--input", "-i", help="标签 CSV"
    ),
    output_json: Path = typer.Option(
        Path("reports/stats/summary.json"), "--output", "-o", help="统计摘要 JSON"
    ),
) -> None:
    """Summarize basic limit-up ecosystem metrics."""
    labeled_bars = _read_csv_or_fail(input_csv)
    required_columns = ["trade_date", "symbol", "is_limit_up", "can_buy_conservative"]
    missing_columns = [column for column in required_columns if column not in labeled_bars.columns]
    if missing_columns:
        raise typer.BadParameter(f"缺失必要列: {missing_columns}")

    total_rows = int(len(labeled_bars))
    limit_up_days = int(labeled_bars["is_limit_up"].sum())
    blocked_buy_days = int(
        (labeled_bars["is_limit_up"] & ~labeled_bars["can_buy_conservative"]).sum()
    )
    summary = {
        "total_rows": total_rows,
        "total_symbols": int(labeled_bars["symbol"].nunique()),
        "limit_up_days": limit_up_days,
        "limit_up_rate": float(limit_up_days / total_rows) if total_rows else 0.0,
        "blocked_buy_days_conservative": blocked_buy_days,
        "blocked_buy_ratio_conservative": float(blocked_buy_days / limit_up_days)
        if limit_up_days
        else 0.0,
    }

    _ensure_parent_directory(output_json)
    output_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    typer.echo(f"Wrote summary stats to {output_json}")


@app.command("report")
def report(
    data_dir: Path = typer.Option(
        Path("data/processed"),
        "--data",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="输入目录（包含 daily.parquet 与 instruments.parquet）",
    ),
    out_dir: Path = typer.Option(
        Path("reports/latest"),
        "--out",
        "-o",
        help="报告输出目录（生成 report.html 与 assets/*.png）",
    ),
) -> None:
    """Generate Phase 1 HTML report with charts and strategy health-check."""
    try:
        artifacts = generate_html_report(data_dir, out_dir)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Wrote report to {artifacts.html_path}")


@app.command("run-demo")
def run_demo(
    out_dir: Path = typer.Option(
        Path("reports/demo"),
        "--out",
        "-o",
        help="Demo 输出目录",
    ),
) -> None:
    """Run demo pipeline with fixtures: ingest -> label -> stats -> report."""
    project_root = _project_root()
    daily_fixture, instruments_fixture = _resolve_demo_fixture_paths(project_root)
    if not daily_fixture.exists():
        raise typer.BadParameter(f"缺少 fixture: {daily_fixture}")
    if not instruments_fixture.exists():
        raise typer.BadParameter(f"缺少 fixture: {instruments_fixture}")

    processed_dir = out_dir / "processed"
    labels_csv = out_dir / "limitup_labels.csv"
    stats_json = out_dir / "summary.json"

    ingest(daily_path=daily_fixture, instruments_path=instruments_fixture, out_dir=processed_dir)
    label(input_csv=daily_fixture, output_csv=labels_csv, limit_ratio=0.10)
    stats(input_csv=labels_csv, output_json=stats_json)
    report(data_dir=processed_dir, out_dir=out_dir)
    typer.echo(f"Demo finished. Open report: {out_dir / 'report.html'}")


@app.command("export-pdf")
def export_pdf(
    html_path: Path = typer.Option(
        Path("reports/demo/index.html"),
        "--html",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="输入 HTML 路径（通常为 report/index 页面）",
    ),
    output_pdf: Path = typer.Option(
        Path("reports/demo/demo.pdf"),
        "--out",
        "-o",
        help="输出 PDF 路径",
    ),
    zip_fallback_path: Path | None = typer.Option(
        Path("reports/demo/demo-html.zip"),
        "--zip-fallback",
        help="PDF 不可用时的 HTML 打包 ZIP（也可作为下载备份）",
    ),
    strict_pdf: bool = typer.Option(
        False,
        "--strict-pdf/--allow-fallback",
        help="若开启 strict-pdf，PDF 导出失败时命令报错。",
    ),
) -> None:
    """Export report HTML to PDF (Playwright) with optional HTML zip fallback."""
    if not html_path.exists():
        raise typer.BadParameter(f"HTML 文件不存在: {html_path}")

    try:
        pdf_created, pdf_message, zipped_bundle_path = _export_report_downloads(
            html_path=html_path,
            pdf_path=output_pdf,
            zip_fallback_path=zip_fallback_path,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if pdf_created:
        typer.echo(pdf_message)
    elif strict_pdf:
        raise typer.BadParameter(pdf_message)
    else:
        typer.echo(pdf_message)

    if zipped_bundle_path is not None:
        typer.echo(f"Wrote HTML bundle zip to {zipped_bundle_path}")


@app.command("build-site")
def build_site(
    demo: bool = typer.Option(
        False,
        "--demo",
        help="是否构建 demo 报告并归档到 site/reports/demo/",
    ),
    out_dir: Path = typer.Option(
        Path("site"),
        "--out",
        "-o",
        help="站点输出目录",
    ),
) -> None:
    """Build static site artifact for Pages deployment."""
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_report_dir: Path | None = None
    if demo:
        demo_report_dir = out_dir / "reports" / "demo"
        run_demo(out_dir=demo_report_dir)
        demo_report_html = demo_report_dir / "index.html"
        _, pdf_message, zipped_bundle_path = _export_report_downloads(
            html_path=demo_report_html,
            pdf_path=out_dir / "demo.pdf",
            zip_fallback_path=out_dir / "demo-html.zip",
        )
        typer.echo(pdf_message)
        if zipped_bundle_path is not None:
            typer.echo(f"Wrote HTML bundle zip to {zipped_bundle_path}")

    case_study_path = _build_case_study_page(out_dir, demo_report_dir)
    landing_path = _build_site_landing(out_dir, demo_report_dir)
    typer.echo(f"Wrote case study to {case_study_path}")
    typer.echo(f"Wrote site landing to {landing_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
