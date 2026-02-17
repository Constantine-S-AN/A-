from pathlib import Path


def test_changelog_contains_v1_release_note() -> None:
    changelog_path = Path("CHANGELOG.md")
    assert changelog_path.exists()

    content = changelog_path.read_text(encoding="utf-8")
    assert "## v1.0.0" in content
    assert "export-pdf" in content
