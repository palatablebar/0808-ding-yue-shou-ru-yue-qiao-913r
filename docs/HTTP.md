# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean` 或 `file=<CSV>` 三选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批和当前复核状态。

`POST /api/stages/balance` 与 `POST /api/runs` 的报告新增 `revenue`：逐组给出 `window`、`opening_cents`、`closing_cents`、`recognized.{numerator,denominator,cents}`、`deferred_numerator` 与 `readback.{forward,segments}`，`checks` 逐项标明是否对平。`balance.blockers` 列明每组阻断状态与记录键，`balance.releasable` 为 `true` 才可签发。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。来源结构问题（`INTERVAL_GAP`、`INTERVAL_OVERLAP`、`ORDER_CONFLICT`、`CHANGE_CONFLICT`）与读回不平（`REVENUE_MISMATCH`）均不可签发。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、业务证据和复核信息的 JSON。
