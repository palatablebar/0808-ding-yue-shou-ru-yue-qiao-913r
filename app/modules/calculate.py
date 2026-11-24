"""月桥拆解：把 prepare 的 payload 转成可读回的收入月桥与旅客/policy 判定。

``measure`` 保留销售视角的期末 MRR 与差额证据（新增、扩张、收缩、流失按整笔金额计），
``revenue`` 给出财务视角的按时段确认结果。两者共用同一组事件，因此可以互相对平。
"""

from app.business import measured
from app.modules.revenue import build


def compute(payload):
    revenue = build(payload)
    totals = revenue["totals"]
    evidence = {f"{kind}_cents": totals[kind]["full"] for kind in totals}
    measure = measured(
        revenue["closing_cents"],
        revenue["closing_anchor_cents"],
        "分",
        evidence,
    )
    return measure, revenue
