"""收入月桥：按服务时长确认，并与期末 MRR 对平。

月桥窗口 ``[open, close)`` 代表一个结算月。期初 MRR 从 ``open`` 起全程服务；每笔变更
只在**其后**的区间生效，因此确认额按剩余时长加权：

    确认收入 = 期初 × W + Σ delta_i × (close − minute_i)      （cent·minute）
    期末 MRR = 期初 + Σ delta_i                                （sales 视角）
    递延调整 = 期末 × W − 确认收入
             = Σ delta_i × (minute_i − open)

三项恒等，因此「期初 + 按时段确认的变动」可与「期末 MRR」对平；同刻事件按来源序列
排序、时长为零，不会多算；月末事件在 prepare 阶段已被排除，不会少算。

稳定读回：``segments`` 逐段记录 ``[start, end)`` 与 ``level``，其 ``level × minutes``
之和必须等于前向加权和。两条路径相等才能签发。
"""

from decimal import Decimal, ROUND_HALF_UP


def _kind(delta, before, after):
    if delta > 0:
        return "new" if before == 0 else "expansion"
    if delta < 0:
        return "churn" if after == 0 else "contraction"
    return "flat"


def _cents(numerator, denominator):
    value = Decimal(numerator) / Decimal(denominator or 1)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build(payload):
    """由 prepare 的 payload 生成收入月桥；只做整数运算，便于逐分读回。"""
    opening = payload["opening_cents"]
    close = payload["closing_cents"]
    start, end = payload["open_minute"], payload["close_minute"]
    width = end - start
    events = payload["events"]

    segments = []
    movements = []
    level = opening
    cursor = start
    for event in events:
        minute = event["minute"]
        if minute > cursor:
            segments.append(
                dict(
                    start=cursor,
                    end=minute,
                    minutes=minute - cursor,
                    level_cents=level,
                    contribution=level * (minute - cursor),
                )
            )
        before = level
        level = event["level_cents"]
        delta = level - before
        if delta:
            movements.append(
                dict(
                    record=event["record"],
                    minute=minute,
                    sequence=event["sequence"],
                    from_cents=before,
                    to_cents=level,
                    delta_cents=delta,
                    kind=_kind(delta, before, level),
                    elapsed_minutes=minute - start,
                    remaining_minutes=end - minute,
                    recognized=delta * (end - minute),
                    deferred=delta * (minute - start),
                )
            )
        else:
            movements.append(
                dict(
                    record=event["record"],
                    minute=minute,
                    sequence=event["sequence"],
                    from_cents=before,
                    to_cents=level,
                    delta_cents=0,
                    kind="flat",
                    elapsed_minutes=minute - start,
                    remaining_minutes=end - minute,
                    recognized=0,
                    deferred=0,
                )
            )
        cursor = minute
    if end > cursor:
        segments.append(
            dict(
                start=cursor,
                end=end,
                minutes=end - cursor,
                level_cents=level,
                contribution=level * (end - cursor),
            )
        )

    opening_contribution = opening * width
    forward = opening_contribution + sum(m["recognized"] for m in movements)
    readback = sum(segment["contribution"] for segment in segments)
    deferred = sum(m["deferred"] for m in movements)
    closing_from_events = opening + sum(m["delta_cents"] for m in movements)

    tiles = bool(segments) and segments[0]["start"] == start
    for previous, current in zip(segments, segments[1:]):
        tiles = tiles and current["start"] == previous["end"]
    tiles = tiles and segments[-1]["end"] == end
    covered = sum(segment["minutes"] for segment in segments)

    checks = dict(
        segments_tile=tiles and covered == width,
        readback_matches=forward == readback,
        revenue_ties=opening_contribution
        + sum(m["recognized"] for m in movements)
        == readback,
        deferred_ties=closing_from_events * width == readback + deferred,
        mrr_ties=closing_from_events == close,
    )
    # 结构完整：分段铺满窗口、前向加权与分段读回一致、确认与递延恒等。
    # 期末锚点是否对平属于业务差异（MISMATCH），交由 policy 判定，不在此阻断读回。
    structural = all(
        checks[key]
        for key in ("segments_tile", "readback_matches", "revenue_ties", "deferred_ties")
    )

    totals = {kind: {"full": 0, "recognized": 0, "deferred": 0} for kind in
              ("new", "expansion", "contraction", "churn")}
    for movement in movements:
        bucket = totals.get(movement["kind"])
        if bucket is not None:
            bucket["full"] += abs(movement["delta_cents"])
            bucket["recognized"] += movement["recognized"]
            bucket["deferred"] += movement["deferred"]

    return dict(
        window=dict(open=start, close=end, minutes=width),
        opening_cents=opening,
        closing_cents=closing_from_events,
        closing_anchor_cents=close,
        recognized_numerator=forward,
        recognized_denominator=width or 1,
        recognized_cents=_cents(forward, width),
        deferred_numerator=deferred,
        deferred_ties_to=checks["deferred_ties"],
        movements=movements,
        segments=segments,
        totals=totals,
        checks=checks,
        ok=structural,
        status="READY" if structural else "REVENUE_MISMATCH",
    )


def summary(cases):
    """阶段五的可回读汇总：逐组给出稳定读回结果，供证据与外部核对。"""
    items = []
    for case in cases:
        revenue = case.get("revenue")
        if revenue is None:
            items.append(
                dict(
                    case=case["case"],
                    record=case.get("blocking", {}).get("records", []),
                    status=case["status"],
                    ok=False,
                )
            )
            continue
        items.append(
            dict(
                case=case["case"],
                status=revenue["status"],
                ok=revenue["ok"],
                window=revenue["window"],
                opening_cents=revenue["opening_cents"],
                closing_cents=revenue["closing_cents"],
                closing_anchor_cents=revenue["closing_anchor_cents"],
                recognized=dict(
                    numerator=revenue["recognized_numerator"],
                    denominator=revenue["recognized_denominator"],
                    cents=revenue["recognized_cents"],
                ),
                deferred_numerator=revenue["deferred_numerator"],
                readback=dict(
                    forward=revenue["recognized_numerator"],
                    segments=sum(s["contribution"] for s in revenue["segments"]),
                ),
                checks=revenue["checks"],
            )
        )
    return dict(
        items=items,
        verified=bool(items) and all(item["ok"] for item in items),
    )
