from __future__ import annotations

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from limitup_lab.cli import app
from limitup_lab.schema import DAILY_BAR_COLUMNS, INSTRUMENT_COLUMNS

runner = CliRunner()
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def test_ingest_with_csv_inputs_writes_canonical_parquet(tmp_path: Path) -> None:
    output_dir = tmp_path / "data" / "processed"
    result = runner.invoke(
        app,
        [
            "ingest",
            "--daily",
            str(FIXTURE_DIR / "daily_bars.csv"),
            "--instruments",
            str(FIXTURE_DIR / "instruments.csv"),
            "--out",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout

    daily_output_path = output_dir / "daily.parquet"
    instruments_output_path = output_dir / "instruments.parquet"
    assert daily_output_path.exists()
    assert instruments_output_path.exists()

    daily_bars = pd.read_parquet(daily_output_path)
    instruments = pd.read_parquet(instruments_output_path)

    assert list(daily_bars.columns) == DAILY_BAR_COLUMNS
    assert list(instruments.columns) == INSTRUMENT_COLUMNS
    assert daily_bars["trade_date"].tolist() == ["20240102", "20240103"]
    assert instruments["board"].tolist() == ["MAIN", "STAR", "BSE"]


def test_ingest_with_parquet_inputs_writes_canonical_parquet(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)

    daily_input_path = input_dir / "daily.parquet"
    instruments_input_path = input_dir / "instruments.parquet"
    pd.read_csv(FIXTURE_DIR / "daily_bars.csv").to_parquet(daily_input_path, index=False)
    pd.read_csv(FIXTURE_DIR / "instruments.csv").to_parquet(instruments_input_path, index=False)

    result = runner.invoke(
        app,
        [
            "ingest",
            "--daily",
            str(daily_input_path),
            "--instruments",
            str(instruments_input_path),
            "--out",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (output_dir / "daily.parquet").exists()
    assert (output_dir / "instruments.parquet").exists()

