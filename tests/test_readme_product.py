from pathlib import Path


def test_readme_contains_product_sections() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8")

    assert "# limitup-lab" in readme_content
    assert "## English" in readme_content
    assert "## 中文版" in readme_content
    assert "Live Demo (GitHub Pages)" in readme_content
    assert "## Screenshots" in readme_content
    assert "## Features" in readme_content
    assert "## Architecture" in readme_content
    assert "## One-Command Demo" in readme_content
    assert "## Limitations & Roadmap" in readme_content


def test_readme_references_required_assets_and_commands() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8")

    assert "assets/readme/hero.png" in readme_content
    assert "assets/readme/tradability-compare.png" in readme_content
    assert "assets/readme/table-preview.png" in readme_content

    assert "ingest" in readme_content
    assert "fetch-akshare" in readme_content
    assert "label" in readme_content
    assert "stats" in readme_content
    assert "backtest" in readme_content
    assert "report" in readme_content
    assert "build-site" in readme_content

    assert "python -m limitup_lab run-demo" in readme_content
    assert "python -m limitup_lab build-site --demo --out site" in readme_content
    assert "python -m limitup_lab fetch-akshare" in readme_content
    assert "分钟线" in readme_content
    assert "L2" in readme_content
    assert "制度变迁" in readme_content
