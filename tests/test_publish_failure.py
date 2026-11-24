"""发布失败时必须保留旧批次的证据，不被覆盖或丢失。

这里的“发布”指把新批次写入历史。旧批次（含其证据）必须保持可读且字节不变，
即使新来源处理失败，也不会影响已有批次。
"""

import io
import json

from conftest import csv_data

from app.evidence.render import artifact
from app.review.service import execute


def rows(*items):
    return [
        [record, "0001", kind, str(minute), str(mrr), str(sequence), "校核"]
        for record, kind, minute, mrr, sequence in items
    ]


def good_source():
    return csv_data(rows(
        ("A1", "opening", 0, 100, 0),
        ("A2", "change", 40, 140, 1),
        ("A3", "close", 100, 140, 0),
    ))


def bad_source():
    return b"record,case,kind,minute\nbroken\n"


def test_failed_publish_keeps_previous_evidence(store):
    previous = execute(store, good_source())
    before = artifact(previous)
    try:
        execute(store, bad_source())
    except Exception:
        pass
    after = artifact(store.load(previous["id"]))
    assert before == after
    assert len(store.list()) == 1


def test_failed_publish_does_not_drop_history(store):
    first = execute(store, good_source())
    second = execute(store, csv_data(rows(
        ("B1", "opening", 0, 50, 0),
        ("B2", "close", 100, 50, 0),
    )))
    assert {item["id"] for item in store.list()} == {first["id"], second["id"]}
    assert artifact(store.load(first["id"])) == artifact(first)


def test_rejected_publish_over_http_keeps_old_run(client):
    run = client.post("/api/runs", data={"sample": "clean"}).json
    before = client.get(f"/api/runs/{run['id']}/evidence").data
    bad = client.post(
        "/api/runs", data={"file": (io.BytesIO(b"wrong,header\n"), "bad.csv")}
    )
    assert bad.status_code == 422
    items = client.get("/api/runs").json["items"]
    assert [item["id"] for item in items] == [run["id"]]
    assert client.get(f"/api/runs/{run['id']}/evidence").data == before
    assert json.loads(before)["schema"] == "review-evidence/1"
