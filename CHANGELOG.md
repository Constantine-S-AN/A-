# Changelog

## v1.0.0 - 2026-02-17

### Added
- `limitup-lab export-pdf` command:
  - Headless HTML to PDF export via Playwright (if available).
  - Built-in `demo-html.zip` fallback bundle for offline download.
- `build-site --demo` now also prepares downloadable artifacts in `site/`:
  - `demo.pdf` (best effort)
  - `demo-html.zip` (fallback)
- GitHub Pages workflow now runs export step after site build:
  - tries to produce `site/demo.pdf`
  - always preserves ZIP fallback path

### Updated
- Site landing page now exposes report download links for PDF/ZIP when present.

### Notes
- This release is focused on research/report usability and distribution.
- No live trading logic is included.
