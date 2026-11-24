"""余额平衡：把金额差异与月桥读回一起作为签收判定。

金额差额给出 ``MISMATCH``；月桥任一分段读回不恒等则给出 ``REVENUE_MISMATCH``，
两者都不允许签发。结构性问题（区间重叠、断档、顺序冲突）在 prepare 已拒绝，此处不再进入。
"""

from app.business import decision


def policy(result, revenue):
    verdict = decision(result)
    if not revenue["ok"]:
        verdict["status"] = "REVENUE_MISMATCH"
        verdict["revenue"] = revenue["checks"]
    return verdict
