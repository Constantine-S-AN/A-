from pathlib import Path
import tomllib


def test_pyproject_contains_parquet_engine_dependency() -> None:
    pyproject_path = Path("pyproject.toml")
    pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dependency_list = pyproject_data["project"]["dependencies"]
    assert any(dependency.startswith("pyarrow") for dependency in dependency_list)


def test_readme_asset_generator_script_exists() -> None:
    script_path = Path("scripts/generate_readme_assets.py")
    assert script_path.exists()

    script_content = script_path.read_text(encoding="utf-8")
    assert "hero.png" in script_content
    assert "tradability-compare.png" in script_content
    assert "table-preview.png" in script_content
