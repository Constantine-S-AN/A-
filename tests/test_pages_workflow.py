from pathlib import Path


def test_pages_workflow_contains_required_steps() -> None:
    workflow_path = Path(".github/workflows/pages.yml")
    assert workflow_path.exists()

    content = workflow_path.read_text(encoding="utf-8")
    assert 'branches: ["main"]' in content
    assert "actions/configure-pages@v5" in content
    assert "actions/upload-pages-artifact@v3" in content
    assert "actions/deploy-pages@v4" in content
    assert "python -m limitup_lab build-site --demo --out site" in content
    assert "python -m limitup_lab export-pdf" in content
    assert "--out site/demo.pdf" in content
    assert "--zip-fallback site/demo-html.zip" in content
    assert "path: site" in content


def test_docs_contain_pages_setup_and_live_demo_link() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8")
    quickstart_content = Path("docs/quickstart.md").read_text(encoding="utf-8")

    assert "github.io" in readme_content
    assert "Settings -> Pages" in quickstart_content
    assert "GitHub Actions" in quickstart_content
