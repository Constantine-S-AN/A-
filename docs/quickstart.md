# Quickstart（使用 fixtures）

## 环境
```bash
python -m pip install -e .
```

## 一键运行（推荐）
```bash
python -m limitup_lab run-demo
```

默认会生成：
- `reports/demo/report.html`
- `reports/demo/assets/*.png`
- `reports/demo/processed/daily.parquet`
- `reports/demo/processed/instruments.parquet`

## 手动跑通流程（ingest -> label -> stats -> report）
```bash
python -m limitup_lab ingest \
  --daily tests/fixtures/daily_bars.csv \
  --instruments tests/fixtures/instruments.csv \
  --out reports/demo/processed

python -m limitup_lab label \
  --input tests/fixtures/daily_bars.csv \
  --output reports/demo/limitup_labels.csv

python -m limitup_lab stats \
  --input reports/demo/limitup_labels.csv \
  --output reports/demo/summary.json

python -m limitup_lab report \
  --data reports/demo/processed \
  --out reports/demo
```

运行完成后打开：
- `reports/demo/report.html`

## 导出 PDF（含 ZIP 兜底）
```bash
python -m limitup_lab export-pdf \
  --html reports/demo/index.html \
  --out reports/demo/demo.pdf \
  --zip-fallback reports/demo/demo-html.zip \
  --allow-fallback
```

说明：
- 若本机可用 Playwright + Chromium，则生成 `demo.pdf`
- 若不可用，命令会保留 `demo-html.zip` 作为可下载兜底

## 发布到 GitHub Pages
1. 确认仓库包含 workflow：`.github/workflows/pages.yml`。
2. 推送到 `main` 后，Actions 会自动执行：
   `python -m limitup_lab build-site --demo --out site`，并发布 `site/`。
3. 在仓库 Settings -> Pages 中，将 Source 设为 `GitHub Actions`。
4. 发布成功后，访问：`https://constantine-s-an.github.io/A-/`。
