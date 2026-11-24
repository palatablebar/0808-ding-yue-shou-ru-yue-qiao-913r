# 订阅收入月桥规则登记

- 规模：中型

## 功能模块

| 模块 | 动作 | 接口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 样例采信 | 预览并定位坏行 | `POST /api/stages/intake` | `app/intake/service.py` | `tests/test_intake.py` |
| M2 变更排序 | 检查领域约束 | `POST /api/stages/prepare` | `app/modules/prepare.py` | `tests/test_prepare.py` |
| M3 月桥拆解 | 查看业务计算结果 | `POST /api/stages/calculate` | `app/modules/calculate.py`、`app/modules/revenue.py` | `tests/test_calculate.py`、`tests/test_revenue.py` |
| M4 余额平衡 | 查看签收判定 | `POST /api/stages/policy` | `app/modules/policy.py` | `tests/test_policy.py` |
| M5 运行对账 | 对照输入、采信和隔离行 | `POST /api/stages/balance` | `app/modules/reconcile.py` | `tests/test_reconcile.py` |
| M6 批次复核 | 执行批次并签发或暂缓 | `POST /api/runs、PATCH /api/runs/<id>` | `app/review/service.py` | `tests/test_review.py` |
| M7 证据交付 | 下载复核清单 | `GET /api/runs/<id>/evidence` | `app/evidence/render.py` | `tests/test_evidence.py` |

## 输入陷阱

| 编号 | 规则 | 处理 | 测试 |
|---|---|---|---|
| TRAP-02 | 去除 BOM | `app/intake/reader.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-03 | 按逻辑记录读取引号内换行 | `app/intake/reader.py` | `tests/test_intake.py::test_quoted_newline_is_one_logical_record` |
| TRAP-04 | 重复表头计入忽略行 | `app/intake/service.py` | `tests/test_intake.py::test_repeated_header_is_counted` |
| TRAP-05 | 异常列数隔离 | `app/intake/schema.py` | `tests/test_intake.py::test_extra_column_is_isolated` |
| TRAP-06 | 归一化全角数字和千分位 | `app/intake/numeric.py` | `tests/test_intake.py::test_full_width_and_grouping_are_canonical` |
| TRAP-07 | 空值行隔离 | `app/intake/numeric.py` | `tests/test_intake.py::test_sentinel_keeps_row_out_of_total` |
| TRAP-08 | 记录键保留前导零 | `app/intake/schema.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-14 | 冲突版本都进入隔离 | `app/intake/resolve.py` | `tests/test_intake.py::test_duplicate_conflict_removes_both_copies` |
| TRAP-16 | 引号未闭合时拒收文件 | `app/intake/reader.py` | `tests/test_intake.py::test_unclosed_quote_invalidates_source` |
| TRAP-18 | 区分空文件、全空白和仅表头 | `app/intake/reader.py` | `tests/test_intake.py::test_empty_states_have_distinct_causes` |
| TRAP-26 | 拒绝旧版本复核 | `app/review/store.py` | `tests/test_review.py::test_review_optimistic_lock` |
| TRAP-27 | 月末事件只影响其后区间 | `app/modules/prepare.py` | `tests/test_revenue.py::test_month_end_change_only_affects_after_window` |
| TRAP-28 | 同刻事件按来源序列、不重复计 | `app/modules/revenue.py` | `tests/test_revenue.py::test_same_minute_events_apply_in_sequence_without_double_count` |
| TRAP-29 | 区间断档/重叠列明记录键并阻断 | `app/modules/prepare.py` | `tests/test_revenue.py::test_two_openings_are_overlap_with_both_keys` |
| TRAP-30 | 同槽位金额/顺序冲突列明记录键 | `app/modules/prepare.py` | `tests/test_revenue.py::test_same_slot_conflicting_amounts_lists_keys` |
| TRAP-31 | 同源重跑不重复确认 | `app/review/service.py` | `tests/test_revenue.py::test_rerun_of_same_bytes_recognizes_once` |
| TRAP-32 | 发布失败保留旧版与证据 | `app/review/store.py` | `tests/test_publish_failure.py` |

## 领域反例

minute 为结算窗口起点后的分钟。月桥使用 [0, close) 半开区间，同一时刻按来源序列执行。新增和重新激活合计，收缩与流失作为减项。

财务视角按服务时长确认：`确认收入 = 期初 × 窗口 + Σ delta × (close − minute)`，并与销售视角的期末 MRR 通过 `期末 × 窗口 = 确认 + 递延` 对平。`revenue.items[].readback` 给出前向和与分段读回和，`checks` 逐项给出是否恒等；任一项不成立则该组非 READY，`balance` 阻止签发。

逐组预期结论见 `tests/test_policy.py`，计算过程证据见 `tests/test_calculate.py` 与 `tests/test_revenue.py`。
