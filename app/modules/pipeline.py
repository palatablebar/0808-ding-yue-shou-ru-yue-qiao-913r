"""阶段编排：采信 → 分组 → 逐组排序、计算、判定 → 运行对账。"""

from app.business import DomainIssue
from app.intake.service import inspect
from app.modules.calculate import compute
from app.modules.grouping import case_groups
from app.modules.policy import policy
from app.modules.prepare import prepare
from app.modules.reconcile import balance
from app.modules.revenue import summary


def evaluate(rows, stage):
    case = {
        "case": rows[0]["case"],
        "records": [r["record"] for r in rows],
        "status": "READY",
    }
    try:
        case["prep"], payload = prepare(rows)
        if stage >= 3:
            case["measure"], case["revenue"] = compute(payload)
        if stage >= 4:
            case.update(policy(case["measure"], case["revenue"]))
    except DomainIssue as error:
        case["status"] = error.code
        case["blocking"] = dict(records=error.records, detail=error.detail)
    return case


def run(data, stage=5):
    intake = inspect(data)
    output = {"intake": {k: v for k, v in intake.items() if k != "rows"}}
    if stage == 1:
        return output
    cases = [evaluate(rows, stage) for _, rows in case_groups(intake["rows"])]
    output["cases"] = cases
    if stage >= 5:
        output["balance"] = balance(intake, cases)
        output["revenue"] = summary(cases)
    return output
