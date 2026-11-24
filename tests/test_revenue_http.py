"""收入月桥在证据与 HTTP 层的贯通。"""

import io
import json

from conftest import csv_data


def rows(*items):
    return [
        [record, "0001", kind, str(minute), str(mrr), str(sequence), "校核"]
        for record, kind, minute, mrr, sequence in items
    ]


def test_evidence_contains_readback_data(store):
    from app.evidence.render import artifact
    from app.review.service import execute

    run = execute(store, csv_data(rows(
        ("A1", "opening", 0, 100, 0),
        ("A2", "change", 40, 140, 1),
        ("A3", "close", 100, 140, 0),
    )))
    packet = json.loads(artifact(run))
    item = packet["revenue"]["items"][0]
    assert item["recognized"]["numerator"] == 100 * 100 + 40 * 60
    assert item["readback"]["forward"] == item["readback"]["segments"]
    assert item["checks"]["mrr_ties"] is True


def test_evidence_lists_blocking_record_keys(store):
    from app.evidence.render import artifact
    from app.review.service import execute

    run = execute(store, csv_data(rows(
        ("B1", "opening", 0, 100, 0),
        ("B2", "change", 40, 120, 4),
        ("B3", "change", 40, 130, 4),
        ("B4", "close", 100, 120, 0),
    )))
    packet = json.loads(artifact(run))
    blocker = packet["balance"]["blockers"][0]
    assert blocker["status"] == "CHANGE_CONFLICT"
    assert sorted(blocker["records"]) == ["B2", "B3"]


def test_conflicting_batch_cannot_be_approved(client):
    data = csv_data(rows(
        ("C1", "opening", 0, 100, 0),
        ("C2", "change", 40, 120, 4),
        ("C3", "change", 40, 130, 4),
        ("C4", "close", 100, 120, 0),
    ))
    run = client.post("/api/runs", data={"file": (io.BytesIO(data), "c.csv")}).json
    assert run["report"]["balance"]["releasable"] is False
    response = client.patch(
        f"/api/runs/{run['id']}",
        json=dict(revision=0, status="APPROVED", note="试图签发冲突来源"),
    )
    assert response.status_code == 409 and response.json["code"] == "UNRESOLVED_ISSUES"


def test_blocking_patch_reports_record_keys(client):
    data = csv_data(rows(
        ("D1", "opening", 0, 100, 0),
        ("D2", "change", 40, 120, 4),
        ("D3", "change", 40, 130, 4),
        ("D4", "close", 100, 120, 0),
    ))
    run = client.post("/api/runs", data={"file": (io.BytesIO(data), "d.csv")}).json
    assert run["report"]["balance"]["blockers"][0]["records"] == ["D2", "D3"]


def test_clean_run_can_be_approved_and_evidence_is_stable(client):
    run = client.post("/api/runs", data={"sample": "clean"}).json
    reviewed = client.patch(
        f"/api/runs/{run['id']}",
        json=dict(revision=0, status="APPROVED", note="来源已复核"),
    )
    assert reviewed.status_code == 200
    first = client.get(f"/api/runs/{run['id']}/evidence").data
    second = client.get(f"/api/runs/{run['id']}/evidence").data
    assert first == second
    assert json.loads(first)["revenue"]["verified"] is True
