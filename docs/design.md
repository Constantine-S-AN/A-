# 研报风格 Design System（Phase 1）

## 1. 目标
- 输出离线可打开的研报样式 HTML，不依赖任何外网 CSS/CDN。
- 样式统一由本地文件 `assets/report.css` 提供。
- 强调“研究报告”视觉：稳重、信息密度高、可打印与可审阅。

## 2. Design Tokens

### 字体
- 正文 `--font-body`:
  - `"Source Han Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif`
- 标题 `--font-heading`:
  - `"Source Han Serif SC", "Songti SC", "STSong", serif`
- 等宽 `--font-mono`:
  - `"JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace`

### 颜色
- 主色 `--color-primary`: `#0f4c81`（标题、关键强调）
- 强调 `--color-accent`: `#c0841a`
- 灰阶：
  - `--color-ink-900`: `#111827`
  - `--color-ink-700`: `#334155`
  - `--color-ink-500`: `#64748b`
  - `--color-line`: `#dbe1ea`
- 状态色：
  - 成功/正收益 `--color-positive`: `#0f7b43`
  - 失败/负收益 `--color-negative`: `#b42318`
- 背景：
  - `--color-bg`: `#f3f6fb`
  - `--color-surface`: `#ffffff`
  - 代码块背景 `--color-code-bg`: `#f6f8fa`

### 间距/圆角/阴影
- 间距：
  - `--space-1: 6px`
  - `--space-2: 12px`
  - `--space-3: 18px`
  - `--space-4: 24px`
  - `--space-5: 32px`
- 圆角：
  - `--radius-sm: 8px`
  - `--radius-md: 12px`
  - `--radius-lg: 18px`
- 阴影：
  - 卡片阴影 `--shadow-card: 0 6px 18px rgba(17, 24, 39, 0.06)`
  - 聚焦阴影 `--shadow-focus: 0 0 0 3px rgba(15, 76, 129, 0.18)`

## 3. 组件规范
- 卡片：
  - 白底、浅描边、轻阴影，突出“模块化研报区块”。
- 表格：
  - 表头浅蓝底、数字右对齐、斑马纹行、数值等宽字体对齐。
- 代码块：
  - 仅用于补充说明与参数片段，使用等宽字体与浅灰背景。
- 图表容器：
  - 统一边框、圆角、标题栏，避免截图拼贴感。

## 4. 离线策略
- 报告模板中仅使用：
  - `<link rel="stylesheet" href="assets/report.css" />`
- `limitup_lab.report.generate_html_report` 会将仓库内 `assets/report.css` 复制到输出目录：
  - `reports/<run_id>/assets/report.css`
- 不使用 Tailwind Play CDN 或其他网络样式源。

## 5. 产出约定
- 报告输出目录至少包含：
  - `index.html`（主入口）
  - `report.html`（兼容旧入口）
  - `assets/report.css`
  - `assets/*.png`（图表）

