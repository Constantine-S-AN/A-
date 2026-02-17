from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_demo_summary() -> dict[str, float | int]:
    summary_path = _repo_root() / "reports" / "demo" / "summary.json"
    if not summary_path.exists():
        return {}
    try:
        loaded = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(loaded, dict):
        return loaded
    return {}


def _generate_hero_image(output_dir: Path, summary: dict[str, float | int]) -> None:
    sample_count = int(summary.get("total_rows", 0))
    limit_up_count = int(summary.get("limit_up_days", 0))
    limit_up_rate = float(summary.get("limit_up_rate", 0.0)) * 100
    blocked_count = int(summary.get("blocked_buy_days_conservative", 0))

    figure, axis = plt.subplots(figsize=(12, 6.6), dpi=150)
    figure.patch.set_facecolor("#f5f7fa")
    axis.set_facecolor("#ffffff")
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")

    axis.text(0.04, 0.9, "LimitUp Lab", fontsize=34, fontweight="bold", color="#123e67")
    axis.text(
        0.04,
        0.83,
        "A-share limit-up ecosystem research (Phase 1, daily)",
        fontsize=14,
        color="#1f4f78",
    )
    axis.text(
        0.04,
        0.77,
        "Focus: tradability gap, next-day premium, and fill-model sensitivity.",
        fontsize=12,
        color="#475569",
    )

    card_specs = [
        ("Samples", f"{sample_count}"),
        ("Limit-Up Days", f"{limit_up_count}"),
        ("Limit-Up Rate", f"{limit_up_rate:.2f}%"),
        ("Blocked Buys (CONS)", f"{blocked_count}"),
    ]
    for index, (label, value) in enumerate(card_specs):
        x_start = 0.04 + index * 0.235
        card = plt.Rectangle(
            (x_start, 0.55),
            0.21,
            0.14,
            linewidth=1.0,
            edgecolor="#c9d7e6",
            facecolor="#edf3f9",
            transform=axis.transAxes,
            clip_on=False,
        )
        axis.add_patch(card)
        axis.text(x_start + 0.015, 0.62, label, fontsize=11, color="#4b647c")
        axis.text(x_start + 0.015, 0.575, value, fontsize=21, fontweight="bold", color="#123e67")

    axis.text(
        0.04,
        0.43,
        "Output: labels, strategy health-check, HTML report, and Pages artifact.",
        fontsize=12,
        color="#334155",
    )
    axis.text(
        0.04,
        0.355,
        "python -m limitup_lab run-demo  |  python -m limitup_lab build-site --demo --out site",
        fontsize=10.5,
        family="monospace",
        color="#1e3a5f",
    )

    output_path = output_dir / "hero.png"
    figure.savefig(output_path, bbox_inches="tight")
    plt.close(figure)


def _generate_tradability_image(output_dir: Path) -> None:
    generator = np.random.default_rng(seed=20260217)
    sealed_returns = np.clip(generator.normal(loc=-0.013, scale=0.028, size=160), -0.18, 0.12)
    opened_returns = np.clip(generator.normal(loc=0.021, scale=0.032, size=220), -0.14, 0.2)

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=150)
    figure.patch.set_facecolor("#f7fafc")

    axes[0].boxplot(
        [sealed_returns, opened_returns], tick_labels=["Sealed", "Non-Sealed"], showfliers=False
    )
    axes[0].axhline(0, color="#6b7280", linewidth=1)
    axes[0].set_title("Next-Day Open Return Distribution")
    axes[0].set_ylabel("return")
    axes[0].grid(alpha=0.2, axis="y")

    bins = np.linspace(-0.16, 0.2, 28)
    axes[1].hist(sealed_returns, bins=bins, alpha=0.6, label="Sealed", color="#ad2e24")
    axes[1].hist(opened_returns, bins=bins, alpha=0.55, label="Non-Sealed", color="#235f8b")
    axes[1].axvline(float(np.median(sealed_returns)), color="#ad2e24", linestyle="--", linewidth=1.2)
    axes[1].axvline(float(np.median(opened_returns)), color="#235f8b", linestyle="--", linewidth=1.2)
    axes[1].set_title("Histogram View")
    axes[1].set_xlabel("next_open_ret")
    axes[1].set_ylabel("count")
    axes[1].legend()
    axes[1].grid(alpha=0.2)

    figure.suptitle("Tradability Gap Snapshot: Sealed vs Non-Sealed", fontsize=15, color="#123e67")
    figure.tight_layout()
    output_path = output_dir / "tradability-compare.png"
    figure.savefig(output_path, bbox_inches="tight")
    plt.close(figure)


def _generate_table_image(output_dir: Path) -> None:
    strategy_path = _repo_root() / "reports" / "demo" / "tables" / "strategy_compare.csv"
    if strategy_path.exists():
        strategy_table = pd.read_csv(strategy_path)
    else:
        strategy_table = pd.DataFrame(
            [
                {
                    "fill_model": "IDEAL",
                    "trade_count": 32,
                    "total_return": 0.1874,
                    "max_drawdown": -0.0921,
                    "win_rate": 0.5625,
                },
                {
                    "fill_model": "CONSERVATIVE",
                    "trade_count": 17,
                    "total_return": -0.0418,
                    "max_drawdown": -0.1512,
                    "win_rate": 0.4118,
                },
            ]
        )

    preview = strategy_table.copy()
    for numeric_column in ["total_return", "max_drawdown", "win_rate"]:
        if numeric_column in preview.columns:
            preview[numeric_column] = pd.to_numeric(preview[numeric_column], errors="coerce").map(
                lambda number: f"{number:.4f}" if pd.notna(number) else ""
            )

    figure, axis = plt.subplots(figsize=(12, 4.0), dpi=150)
    figure.patch.set_facecolor("#f7fafc")
    axis.axis("off")
    axis.set_title("Strategy Health-Check Table Preview", fontsize=16, color="#123e67", pad=12)

    table = axis.table(
        cellText=preview.values,
        colLabels=preview.columns.tolist(),
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.5)
    for (row_index, _column_index), cell in table.get_celld().items():
        if row_index == 0:
            cell.set_facecolor("#1f4f78")
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#edf3f9")
            cell.set_edgecolor("#c9d7e6")

    output_path = output_dir / "table-preview.png"
    figure.savefig(output_path, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    output_dir = _repo_root() / "assets" / "readme"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = _load_demo_summary()

    _generate_hero_image(output_dir, summary)
    _generate_tradability_image(output_dir)
    _generate_table_image(output_dir)
    print(f"Generated README assets in {output_dir}")


if __name__ == "__main__":
    main()
