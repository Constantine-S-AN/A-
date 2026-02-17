# A 股涨停板生态研究规范（Phase 1, 日频）

## 1. 范围与目标
- 本项目仅用于研究与策略体检，不包含任何实盘交易逻辑。
- 频率为日线（Phase 1），不使用分钟线盘口数据。
- 输出包括：
  - 标准化数据（`data/processed/*.parquet`）
  - 标签与统计（CSV/JSON）
  - HTML 报告（含图片）

## 2. Canonical Schema
- `DailyBar`:
  - `ts_code`, `trade_date(YYYYMMDD)`, `open`, `high`, `low`, `close`, `pre_close`, `vol`, `amount`
- `Instrument`:
  - `ts_code`, `name(optional)`, `board(MAIN/STAR/CHINEXT/BSE/UNKNOWN)`, `is_st(bool)`, `list_date(optional)`

## 3. 涨跌幅规则与适用性
- 规则文件：`config/limit_rules.toml`
  - `MAIN`: `limit_up=0.10`, `limit_down=0.10`, `ipo_unlimited_days=1`
  - `ST`: `limit_up=0.05`, `limit_down=0.05`, `ipo_unlimited_days=1`
  - `STAR`: `limit_up=0.20`, `limit_down=0.20`, `ipo_unlimited_days=5`
  - `CHINEXT`: `limit_up=0.20`, `limit_down=0.20`, `ipo_unlimited_days=5`
- `compute_limit_price(pre_close, up)`:
  - 使用 `Decimal`，按 `0.01` 四舍五入。
- `is_price_limit_applicable(instrument_row, trade_date)`:
  - 粗略按 `list_date + ipo_unlimited_days` 判断是否适用涨跌幅；
  - `list_date` 缺失时默认 `True`。

截至 2026-02-17，SSE 官方机制页说明 A 股一般为 10%，风险警示股票为 5%，且上市首日等情形可不受涨跌幅限制。项目中的 `MAIN/ST` 基线来自该规则；其余板块通过配置可调整。  
参考：[SSE Trading Mechanism](https://english.sse.com.cn/start/trading/mechanism/)

## 4. 标签定义（日频近似）
- `limit_up_price`:
  - 基于 `pre_close * (1 + limit_up)` 计算。
- `label_limit_up`:
  - `close ≈ limit_up_price` 且 `high ≈ limit_up_price` 且 `price_limit_applicable=True`。
- `label_one_word`:
  - `open ≈ high ≈ low ≈ close ≈ limit_up_price`（一字板日频近似）。
- `label_opened`:
  - `high ≈ limit_up_price` 且 `low < limit_up_price - eps`（开板日频近似）。
- `label_sealed`:
  - `label_limit_up=True` 且 `label_opened=False`（封死日频近似）。
- `streak_up`:
  - 同一 `ts_code` 连续涨停计数，非涨停归零；
  - 若中间缺失市场交易日，视为断板并重置。

## 5. 过滤规则
- `exclude_unlimited_days`:
  - 过滤掉不适用涨跌幅限制的日期。
- `exclude_suspended`:
  - 使用 `vol==0` 近似停牌过滤；
  - 原始日线缺失天然不进入样本。

## 6. 次日收益与分组统计
- `next_open_ret`:
  - `next_open / close - 1`
- `next_close_ret`:
  - `next_close / close - 1`
- 每个 `ts_code` 最后一个交易日无 next-day 数据，记为 `NaN`。
- 分组统计默认按 `board/is_st/streak_up/one_word/opened` 输出：
  - `count`, `mean`, `p10`, `p50`, `p90`

## 7. Fill 假设（体检维度）
- `IDEAL`:
  - 涨停日视为可在 `close` 成交（研究上限）。
- `CONSERVATIVE`:
  - 若 `label_sealed=True` 或 `label_one_word=True`，视为不可买；
  - 其他涨停日可买，价格先用 `close`（后续可扩展）。

## 8. 回测与策略插件约束
- 策略接口仅依赖标准列：
  - `label_limit_up`, `streak_up`, `label_one_word`, `label_sealed`，及 `ts_code/trade_date/open/close`
- 回测输出：
  - `trades`（含 `entry/exit` 与 `ret_net`）
  - `equity_curve`
- 成本模型：
  - entry/exit 双边按 `fee_bps + slippage_bps` 调整。

## 9. 数据字段来源（未来线上扩展）
- 离线输入优先，Tushare/AkShare 为可选 adapter。
- Tushare `daily` 接口字段可映射到本项目 canonical schema。  
参考：[Tushare Pro 文档（daily）](https://tushare.pro/document/2?doc_id=27)

## 10. 已知限制
- 日频标签是近似定义，不能等价还原盘中“封单质量/炸板次数/回封节奏”。
- `is_price_limit_applicable` 仅基于 `list_date+ipo_days` 粗略判断，未覆盖复牌、临停、交易所临时规则等事件。
- Fill 假设不代表可成交真实性，主要用于识别“回测幻觉”区间。
