# 真实数据接入与应用示例（AkShare）

## 1) 安装
```bash
python -m pip install -e .
python -m pip install akshare
```

## 2) 拉取真实 A 股日线
下面示例用 3 只股票构建一个“涨停生态”研究样本：

```bash
python -m limitup_lab fetch-akshare \
  --symbols 002261.SZ,603598.SH,000957.SZ \
  --start 20240101 \
  --end 20240630 \
  --out data/processed/real_case_2024h1
```

输出：
- `data/processed/real_case_2024h1/daily.parquet`
- `data/processed/real_case_2024h1/instruments.parquet`

说明：
- 默认 `--without-names`（更快）
- 若需要名称与 ST 推断，可加 `--with-names`

## 3) 生成研究报告
```bash
python -m limitup_lab report \
  --data data/processed/real_case_2024h1 \
  --out reports/real_case_2024h1
```

可选导出 PDF：
```bash
python -m limitup_lab export-pdf \
  --html reports/real_case_2024h1/index.html \
  --out reports/real_case_2024h1/report.pdf \
  --zip-fallback reports/real_case_2024h1/report-html.zip \
  --allow-fallback
```

## 4) 真实应用例子
场景：你想回答“连板高低与次日溢价是否分层，以及可交易性假设会不会改变策略结论”。

执行上面两条命令后，重点看：
- `reports/real_case_2024h1/index.html` 的 `Premium` 章节：
  查看 `streak_up` 分组后的 `next_open_ret` 分位数。
- `Tradability` 章节：
  看封死/非封死样本的溢价差异。
- `Sensitivity` 章节：
  对比 `IDEAL` vs `CONSERVATIVE` 的 `total_return` 与 `max_drawdown`。

这就是一个可直接复现的“真实数据 -> 标签 -> 体检报告”闭环。

## 5) 一次真实跑数样例（2026-02-17）
以下是本仓库在真实拉取后的一个示例结果（区间：`20240101~20240229`，股票池：`002261.SZ,603598.SH,000957.SZ`）：

`strategy_compare.csv`

| fill_model | trade_count | total_return | max_drawdown | win_rate |
|---|---:|---:|---:|---:|
| IDEAL | 4 | 0.223679 | 0.0 | 1.0 |
| CONSERVATIVE | 4 | 0.223679 | 0.0 | 1.0 |

解释：
- 这个样本期内，策略触发的首板样本以“可买入”场景为主，因此 IDEAL/CONSERVATIVE 暂未分化。
- 真实研究中可以扩大股票池（例如 20~100 只）并拉长窗口，通常会看到可交易性假设带来的差异。
