from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
from typer.testing import CliRunner

from limitup_lab.cli import app

runner = CliRunner()


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _write_sample_bars(csv_path: Path) -> None:
    sample_bars = pd.DataFrame(
        [
            {
                "trade_date": "2024-01-02",
                "symbol": "AAA",
                "open": 10.0,
                "high": 10.0,
                "low": 9.8,
                "close": 10.0,
                "volume": 1000,
            },
            {
                "trade_date": "2024-01-03",
                "symbol": "AAA",
                "open": 10.5,
                "high": 11.0,
                "low": 10.5,
                "close": 11.0,
                "volume": 1200,
            },
            {
                "trade_date": "2024-01-02",
                "symbol": "BBB",
                "open": 20.0,
                "high": 20.0,
                "low": 19.9,
                "close": 20.0,
                "volume": 2000,
            },
            {
                "trade_date": "2024-01-03",
                "symbol": "BBB",
                "open": 21.0,
                "high": 22.0,
                "low": 20.8,
                "close": 21.8,
                "volume": 2200,
            },
        ]
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    sample_bars.to_csv(csv_path, index=False)


def test_cli_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.stdout
    assert "fetch-akshare" in result.stdout
    assert "label" in result.stdout
    assert "stats" in result.stdout
    assert "report" in result.stdout
    assert "run-demo" in result.stdout
    assert "export-pdf" in result.stdout
    assert "build-site" in result.stdout


def test_module_entry_help() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    source_path = str(project_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{source_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else source_path
    result = subprocess.run(
        [sys.executable, "-m", "limitup_lab", "--help"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ingest" in result.stdout
    assert "fetch-akshare" in result.stdout
    assert "label" in result.stdout
    assert "stats" in result.stdout
    assert "report" in result.stdout
    assert "run-demo" in result.stdout
    assert "export-pdf" in result.stdout
    assert "build-site" in result.stdout


def test_pipeline_generates_labels_stats_and_report(tmp_path: Path) -> None:
    raw_csv = tmp_path / "input" / "daily.csv"
    labeled_csv = tmp_path / "data" / "processed" / "limitup_labels.csv"
    stats_json = tmp_path / "reports" / "stats" / "summary.json"
    processed_input_dir = tmp_path / "processed_input"
    report_dir = tmp_path / "reports" / "run_001"
    index_html = report_dir / "index.html"
    report_html = report_dir / "report.html"
    report_css = report_dir / "assets" / "report.css"
    streak_chart_png = report_dir / "assets" / "streak_next_close_p50.png"
    hist_chart_png = report_dir / "assets" / "next_open_ret_hist.png"
    equity_chart_png = report_dir / "assets" / "equity_compare.png"

    _write_sample_bars(raw_csv)

    label_result = runner.invoke(
        app,
        ["label", "--input", str(raw_csv), "--output", str(labeled_csv)],
    )
    assert label_result.exit_code == 0
    assert labeled_csv.exists()

    labeled_bars = pd.read_csv(labeled_csv)
    aaa_limit_row = labeled_bars[
        (labeled_bars["symbol"] == "AAA") & (labeled_bars["trade_date"] == "2024-01-03")
    ].iloc[0]
    bbb_limit_row = labeled_bars[
        (labeled_bars["symbol"] == "BBB") & (labeled_bars["trade_date"] == "2024-01-03")
    ].iloc[0]

    assert _to_bool(aaa_limit_row["is_limit_up"])
    assert _to_bool(aaa_limit_row["is_sealed_limit"])
    assert _to_bool(aaa_limit_row["can_buy_ideal"])
    assert not _to_bool(aaa_limit_row["can_buy_conservative"])

    assert _to_bool(bbb_limit_row["is_limit_up"])
    assert not _to_bool(bbb_limit_row["is_sealed_limit"])
    assert _to_bool(bbb_limit_row["can_buy_conservative"])

    stats_result = runner.invoke(
        app,
        ["stats", "--input", str(labeled_csv), "--output", str(stats_json)],
    )
    assert stats_result.exit_code == 0
    assert stats_json.exists()

    summary = json.loads(stats_json.read_text(encoding="utf-8"))
    assert summary["total_rows"] == 4
    assert summary["total_symbols"] == 2
    assert summary["limit_up_days"] == 2
    assert summary["blocked_buy_days_conservative"] == 1

    ingest_result = runner.invoke(
        app,
        [
            "ingest",
            "--daily",
            str(Path(__file__).resolve().parent / "fixtures" / "daily_bars.csv"),
            "--instruments",
            str(Path(__file__).resolve().parent / "fixtures" / "instruments.csv"),
            "--out",
            str(processed_input_dir),
        ],
    )
    assert ingest_result.exit_code == 0

    report_result = runner.invoke(
        app,
        ["report", "--data", str(processed_input_dir), "--out", str(report_dir)],
    )
    assert report_result.exit_code == 0
    assert index_html.exists()
    assert report_html.exists()
    assert report_css.exists()
    assert streak_chart_png.exists()
    assert hist_chart_png.exists()
    assert equity_chart_png.exists()


def test_fetch_akshare_command_writes_parquet(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "real"

    def fake_fetch_akshare_dataset(
        ts_codes: list[str],
        start_date: str,
        end_date: str,
        adjust: str,
        include_names: bool,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        assert ts_codes == ["002261.SZ", "603598.SH"]
        assert start_date == "20240101"
        assert end_date == "20240131"
        assert adjust == ""
        assert not include_names
        daily_bars = pd.DataFrame(
            [
                {
                    "ts_code": "002261.SZ",
                    "trade_date": "20240102",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.9,
                    "close": 10.2,
                    "pre_close": 10.0,
                    "vol": 100000.0,
                    "amount": 1020000.0,
                }
            ]
        )
        instruments = pd.DataFrame(
            [
                {
                    "ts_code": "002261.SZ",
                    "name": "拓维信息",
                    "board": "MAIN",
                    "is_st": False,
                    "list_date": "20080723",
                },
                {
                    "ts_code": "603598.SH",
                    "name": "引力传媒",
                    "board": "MAIN",
                    "is_st": False,
                    "list_date": "20150527",
                },
            ]
        )
        return daily_bars, instruments

    monkeypatch.setattr("limitup_lab.cli.fetch_akshare_dataset", fake_fetch_akshare_dataset)
    result = runner.invoke(
        app,
        [
            "fetch-akshare",
            "--symbols",
            "002261.SZ,603598.SH",
            "--start",
            "20240101",
            "--end",
            "20240131",
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    daily_output = out_dir / "daily.parquet"
    instruments_output = out_dir / "instruments.parquet"
    assert daily_output.exists()
    assert instruments_output.exists()
    assert "Wrote canonical daily bars" in result.stdout
    assert "Wrote canonical instruments" in result.stdout


def test_run_demo_generates_html_report(tmp_path: Path) -> None:
    out_dir = tmp_path / "demo"
    result = runner.invoke(app, ["run-demo", "--out", str(out_dir)])
    assert result.exit_code == 0
    assert (out_dir / "index.html").exists()
    assert (out_dir / "report.html").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "assets" / "report.css").exists()
    assert (out_dir / "assets" / "streak_next_close_p50.png").exists()
    assert (out_dir / "assets" / "next_open_ret_hist.png").exists()
    assert (out_dir / "assets" / "equity_compare.png").exists()
    assert (out_dir / "tables" / "strategy_compare.csv").exists()

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["limit_up_days"] > 0

    strategy_compare = pd.read_csv(out_dir / "tables" / "strategy_compare.csv")
    assert not strategy_compare.empty
    assert strategy_compare["trade_count"].sum() > 0


def test_export_pdf_writes_zip_fallback(tmp_path: Path) -> None:
    report_dir = tmp_path / "demo_report"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = report_dir / "index.html"
    html_path.write_text("<html><body><h1>demo</h1></body></html>", encoding="utf-8")

    output_pdf = tmp_path / "download" / "demo.pdf"
    output_zip = tmp_path / "download" / "demo-html.zip"
    result = runner.invoke(
        app,
        [
            "export-pdf",
            "--html",
            str(html_path),
            "--out",
            str(output_pdf),
            "--zip-fallback",
            str(output_zip),
            "--allow-fallback",
        ],
    )
    assert result.exit_code == 0
    assert output_zip.exists()
    assert "Wrote HTML bundle zip" in result.stdout


def test_build_site_demo_generates_landing_and_archived_report(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    result = runner.invoke(app, ["build-site", "--demo", "--out", str(site_dir)])
    assert result.exit_code == 0

    landing_page = site_dir / "index.html"
    case_study_page = site_dir / "case-study.html"
    demo_report_dir = site_dir / "reports" / "demo"
    landing_css = site_dir / "assets" / "report.css"
    image_dir = site_dir / "assets" / "images"

    assert landing_page.exists()
    assert case_study_page.exists()
    assert landing_css.exists()
    assert (site_dir / "demo-html.zip").exists()
    assert (demo_report_dir / "index.html").exists()
    assert (demo_report_dir / "report.html").exists()
    summary = json.loads((demo_report_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["limit_up_days"] > 0
    assert (demo_report_dir / "assets" / "streak_next_close_p50.png").exists()
    assert (demo_report_dir / "assets" / "sealed_vs_nonsealed_premium.png").exists()
    assert (demo_report_dir / "assets" / "equity_compare.png").exists()

    landing_html = landing_page.read_text(encoding="utf-8")
    assert "reports/demo/index.html" in landing_html
    assert "case-study.html" in landing_html
    assert "demo-html.zip" in landing_html
    case_html = case_study_page.read_text(encoding="utf-8")
    assert "三个可复现结论" in case_html
    assert "回测幻觉示例" in case_html
    assert "IDEAL" in case_html
    assert "CONSERVATIVE" in case_html
    assert "分钟线与 L2" in case_html
    assert (image_dir / "streak_next_close_p50.png").exists()
    assert (image_dir / "sealed_vs_nonsealed_premium.png").exists()
    assert (image_dir / "equity_compare.png").exists()
    assert (image_dir / "backtest_illusion_example.png").exists()
