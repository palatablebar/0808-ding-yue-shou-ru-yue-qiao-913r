# 字段与业务定义

输入编码 UTF-8，允许 BOM。首行必须匹配样例列顺序。记录键和业务组保留原始字符串。`kind` 允许 opening, change, close。说明列 `note` 可以跨行，限制 200 字。

业务字段按 `minute`、`mrr_cents`、`sequence` 排列。数字接受非负整数、全角数字和完整千分位。空串、短横线、N/A、NULL 与未知为缺值。无关字段用 0 占位。

minute 为结算窗口起点后的分钟。月桥使用 [0, close) 半开区间，同一时刻按来源序列执行。新增和重新激活合计，收缩与流失作为减项。

## 收入确认

- 期初 MRR 从窗口起点起全程服务，确认 `期初 × 窗口分钟`。
- 每笔变更只在**其后**的区间生效，确认 `delta × (close − minute)`。月末（`minute == close`）及之后的事件属于下月，不计入本月。
- 同刻事件按 `sequence` 依次执行，中间时长为零，不会重复计入。
- 恒等式：`期末 MRR × 窗口 = 确认收入 + 递延调整`，其中递延调整 `= Σ delta × (minute − open)`。
- 读回：逐段记录 `[start, end)` 与 `level`，`Σ level × 分钟` 必须等于前向加权和；两条路径一致才可签发。

## 阻断与记录键

区间断档（`INTERVAL_GAP`）、区间重叠（`INTERVAL_OVERLAP`）、顺序冲突（`ORDER_CONFLICT`）、时刻金额冲突（`CHANGE_CONFLICT`）都会在 `balance.blockers` 中列明记录键并阻止签发。月末与窗口外事件写入 `prep.details.excluded_events`，不参与本月确认。

`incoming.csv` 包含四个业务组，第二组提供不同边界，第三组触发业务拒收，第四组需要核对。另含重复表头、冲突记录、重复回放与错误列数。`ready.csv` 含可以签发的两个组。
