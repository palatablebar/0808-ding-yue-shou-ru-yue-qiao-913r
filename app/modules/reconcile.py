"""运行对账：输入行守恒、业务组状态汇总与签发门槛。

``releasable`` 同时要求：行数守恒、无隔离行、全部业务组通过、且月桥读回已验证。
结构化问题（重叠、断档、冲突）会以非 READY 状态进入 ``issues`` 与 ``blockers``，
``blockers`` 逐条列明记录键，从而阻断签发。
"""

from collections import Counter

# 这些状态属于来源结构问题，必须列明记录键后才能修复重跑。
STRUCTURAL = {
    "INTERVAL_GAP",
    "INTERVAL_OVERLAP",
    "INVALID_PERIOD",
    "ORDER_CONFLICT",
    "CHANGE_CONFLICT",
    "EXPECTED_ONE_OPENING",
    "EXPECTED_ONE_CLOSE",
}


def _blockers(cases):
    items = []
    for case in cases:
        if case["status"] == "READY":
            continue
        blocking = case.get("blocking", {})
        items.append(
            dict(
                case=case["case"],
                status=case["status"],
                structural=case["status"] in STRUCTURAL,
                records=list(blocking.get("records", [])),
                detail=blocking.get("detail"),
                evidence_records=list(case.get("records", [])),
            )
        )
    return sorted(items, key=lambda item: (item["case"], item["status"]))


def balance(intake, cases):
    accounted = (
        intake["accepted"] + intake["rejected"] + intake["blank"] + intake["repeated"]
    )
    status = Counter(case["status"] for case in cases)
    ready = status.pop("READY", 0)
    observed = sum(len(case["records"]) for case in cases)
    verified = bool(cases) and all(
        case.get("revenue", {}).get("ok", False) for case in cases
    )
    blockers = _blockers(cases)
    isolated = intake["rejected"]
    checks = dict(
        input=intake["input"],
        accepted=intake["accepted"],
        isolated=isolated,
        ignored=intake["blank"] + intake["repeated"],
        accounted=accounted,
        balanced=accounted == intake["input"] and observed == intake["accepted"],
        ready=ready,
        pending=len(cases) - ready,
        verified=verified,
        issues=dict(sorted(status.items())),
        blockers=blockers,
        releasable=bool(cases)
        and ready == len(cases)
        and verified
        and not isolated
        and accounted == intake["input"]
        and observed == intake["accepted"],
    )
    return checks
