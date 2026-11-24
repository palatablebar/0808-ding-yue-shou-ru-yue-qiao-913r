"""变更排序：把点状变更整理成可确认的服务区间。

月桥窗口是 ``[0, close)`` 的半开区间。月初行必须落在 0；月末（``minute == close``）
及之后的事件只影响其后区间，因此不进入本月。同一时刻的多个事件按来源 ``sequence``
依次执行，每一笔只作用于其后的分钟数，不回溯、不重复。

任何使区间无法唯一划分的来源问题都在这里拒绝，并带上记录键：

- ``INTERVAL_GAP``：缺少期初/期末锚点，或月初行不在 0，``[0, open)`` 无人服务。
- ``INTERVAL_OVERLAP``：同时存在多个期初或期末锚点，边界定义重叠。
- ``INVALID_PERIOD``：期末不晚于期初，窗口为空。
- ``ORDER_CONFLICT``：同一 ``(minute, sequence)`` 槽位出现两条不同记录。
- ``CHANGE_CONFLICT``：同一槽位的两条记录金额不同，无法判定应执行哪一笔。
"""

from collections import defaultdict

from app.business import DomainIssue, by_kind, prepared


def _keys(rows):
    return [row["record"] for row in rows]


def _anchors(rows):
    opening, close = by_kind(rows, "opening"), by_kind(rows, "close")
    if not opening or not close:
        missing = "opening" if not opening else "close"
        raise DomainIssue(
            "INTERVAL_GAP", _keys(opening + close), detail={"missing": missing}
        )
    if len(opening) > 1 or len(close) > 1:
        duplicated = (opening if len(opening) > 1 else []) + (
            close if len(close) > 1 else []
        )
        raise DomainIssue(
            "INTERVAL_OVERLAP",
            _keys(duplicated),
            detail={"opening": len(opening), "close": len(close)},
        )
    return opening[0], close[0]


def _events(rows, start, end):
    """按 (minute, sequence) 排出窗口内事件；窗口外事件保留为 excluded。"""
    slots = defaultdict(list)
    excluded = []
    for row in by_kind(rows, "change"):
        if not start <= row["minute"] < end:
            excluded.append(
                dict(
                    record=row["record"],
                    minute=row["minute"],
                    sequence=row["sequence"],
                    reason="OUTSIDE_WINDOW",
                )
            )
            continue
        slots[(row["minute"], row["sequence"])].append(row)

    events = []
    for slot in sorted(slots):
        records = slots[slot]
        amounts = {row["mrr_cents"] for row in records}
        if len(records) > 1:
            code = "CHANGE_CONFLICT" if len(amounts) > 1 else "ORDER_CONFLICT"
            raise DomainIssue(
                code,
                _keys(records),
                detail={
                    "minute": slot[0],
                    "sequence": slot[1],
                    "amounts": sorted(amounts),
                },
            )
        row = records[0]
        events.append(
            dict(
                record=row["record"],
                minute=row["minute"],
                sequence=row["sequence"],
                level_cents=row["mrr_cents"],
            )
        )
    return events, sorted(excluded, key=lambda item: (item["minute"], item["sequence"]))


def prepare(rows):
    base, close = _anchors(rows)
    if base["minute"] != 0:
        raise DomainIssue(
            "INTERVAL_GAP",
            [base["record"]],
            detail={"missing_from": 0, "missing_to": base["minute"]},
        )
    if base["minute"] >= close["minute"]:
        raise DomainIssue(
            "INVALID_PERIOD", [base["record"], close["record"]]
        )

    events, excluded = _events(rows, base["minute"], close["minute"])
    payload = dict(
        opening_cents=base["mrr_cents"],
        closing_cents=close["mrr_cents"],
        open_minute=base["minute"],
        close_minute=close["minute"],
        opening_record=base["record"],
        closing_record=close["record"],
        events=events,
        excluded=excluded,
    )
    return prepared(
        len(events),
        {
            "opening_cents": base["mrr_cents"],
            "closing_boundary": close["minute"],
            "closing_cents": close["mrr_cents"],
            "window_minutes": close["minute"] - base["minute"],
            "excluded_events": len(excluded),
        },
        payload,
    )
