"""收入月桥：按时段确认、读回对平与签发门槛。"""

from conftest import csv_data

from app.intake.service import inspect
from app.modules.pipeline import run


def rows(*items):
    """items: (record, kind, minute, mrr, sequence)。"""
    return [
        [record, "0001", kind, str(minute), str(mrr), str(sequence), "校核"]
        for record, kind, minute, mrr, sequence in items
    ]


def compute(*items):
    data = csv_data(rows(*items))
    return run(data, 3)["cases"][0]


def revenue(*items):
    return compute(*items)["revenue"]


def test_recognition_is_prorated_by_remaining_minutes():
    rev = revenue(
        ("A1", "opening", 0, 100, 0),
        ("A2", "change", 40, 140, 1),
        ("A3", "close", 100, 140, 0),
    )
    assert rev["window"] == {"open": 0, "close": 100, "minutes": 100}
    assert rev["recognized_numerator"] == 100 * 100 + 40 * 60
    assert rev["recognized_cents"] == 124
    assert rev["closing_cents"] == 140
    assert rev["checks"]["mrr_ties"] is True
    assert rev["ok"] is True


def test_opening_is_recognized_for_full_window():
    rev = revenue(
        ("B1", "opening", 0, 1000, 0),
        ("B2", "close", 60, 1000, 0),
    )
    assert rev["recognized_numerator"] == 1000 * 60
    assert rev["recognized_cents"] == 1000


def test_month_end_change_only_affects_after_window():
    rev = revenue(
        ("C1", "opening", 0, 100, 0),
        ("C2", "change", 90, 200, 1),
        ("C3", "change", 100, 50, 9),  # 期末同刻，属于其后区间
        ("C4", "close", 100, 200, 0),
    )
    assert [m["record"] for m in rev["movements"]] == ["C2"]
    assert rev["closing_cents"] == 200
    assert rev["checks"]["mrr_ties"] is True


def test_same_minute_events_apply_in_sequence_without_double_count():
    rev = revenue(
        ("D1", "opening", 0, 100, 0),
        ("D2", "change", 50, 160, 1),
        ("D3", "change", 50, 120, 2),
        ("D4", "close", 100, 120, 0),
    )
    recognized = 100 * 50 + 160 * 0 + 120 * 50
    assert rev["recognized_numerator"] == recognized
    assert rev["checks"]["readback_matches"] is True
    assert rev["checks"]["mrr_ties"] is True
    assert [m["delta_cents"] for m in rev["movements"]] == [60, -40]


def test_segments_tile_the_window_and_tie_to_forward_sum():
    rev = revenue(
        ("E1", "opening", 0, 10, 0),
        ("E2", "change", 30, 30, 1),
        ("E3", "change", 70, 20, 2),
        ("E4", "close", 100, 20, 0),
    )
    segments = rev["segments"]
    assert segments[0]["start"] == 0 and segments[-1]["end"] == 100
    for previous, current in zip(segments, segments[1:]):
        assert current["start"] == previous["end"]
    assert sum(s["contribution"] for s in segments) == rev["recognized_numerator"]


def test_deferred_identity_holds():
    rev = revenue(
        ("F1", "opening", 0, 100, 0),
        ("F2", "change", 20, 150, 1),
        ("F3", "change", 80, 90, 2),
        ("F4", "close", 100, 90, 0),
    )
    width = rev["window"]["minutes"]
    assert rev["closing_cents"] * width == rev["recognized_numerator"] + rev["deferred_numerator"]
    assert rev["checks"]["deferred_ties"] is True


def test_missing_close_is_a_gap_with_record_key():
    item = compute(("G1", "opening", 0, 100, 0), ("G2", "change", 10, 110, 1))
    assert item["status"] == "INTERVAL_GAP"
    assert item["blocking"]["detail"]["missing"] == "close"


def test_opening_not_at_zero_is_a_gap():
    item = compute(
        ("H1", "opening", 5, 100, 0),
        ("H2", "close", 100, 120, 0),
    )
    assert item["status"] == "INTERVAL_GAP"
    assert item["blocking"]["records"] == ["H1"]


def test_two_openings_are_overlap_with_both_keys():
    item = compute(
        ("I1", "opening", 0, 100, 0),
        ("I2", "opening", 0, 100, 1),
        ("I3", "close", 100, 120, 0),
    )
    assert item["status"] == "INTERVAL_OVERLAP"
    assert sorted(item["blocking"]["records"]) == ["I1", "I2"]


def test_same_slot_conflicting_amounts_lists_keys():
    item = compute(
        ("J1", "opening", 0, 100, 0),
        ("J2", "change", 40, 120, 4),
        ("J3", "change", 40, 130, 4),
        ("J4", "close", 100, 120, 0),
    )
    assert item["status"] == "CHANGE_CONFLICT"
    assert sorted(item["blocking"]["records"]) == ["J2", "J3"]


def test_same_slot_same_amount_but_two_records_is_order_conflict():
    item = compute(
        ("K1", "opening", 0, 100, 0),
        ("K2", "change", 40, 120, 4),
        ("K3", "change", 40, 120, 4),
        ("K4", "close", 100, 120, 0),
    )
    assert item["status"] == "ORDER_CONFLICT"
    assert sorted(item["blocking"]["records"]) == ["K2", "K3"]


def test_out_of_window_changes_are_reported_not_counted():
    item = compute(
        ("L1", "opening", 0, 100, 0),
        ("L2", "change", 200, 140, 1),
        ("L3", "close", 100, 100, 0),
    )
    assert item["status"] == "READY"
    assert item["prep"]["details"]["excluded_events"] == 1
    assert item["revenue"]["closing_cents"] == 100


def test_dirty_sample_blocks_structural_and_mismatch():
    import pathlib

    data = pathlib.Path(__file__).resolve().parents[1] / "sample_data" / "incoming.csv"
    report = run(data.read_bytes(), 5)
    blocked = {item["case"]: item for item in report["balance"]["blockers"]}
    assert blocked["0003"]["status"] == "CHANGE_CONFLICT"
    assert "000302" in blocked["0003"]["records"]
    assert blocked["0004"]["status"] == "MISMATCH"
    assert report["balance"]["releasable"] is False
    assert report["revenue"]["verified"] is False


def test_clean_sample_reads_back_and_is_releasable():
    import pathlib

    data = pathlib.Path(__file__).resolve().parents[1] / "sample_data" / "ready.csv"
    report = run(data.read_bytes(), 5)
    assert report["balance"]["releasable"] is True
    assert report["revenue"]["verified"] is True
    assert all(item["readback"]["forward"] == item["readback"]["segments"]
               for item in report["revenue"]["items"])


def test_rerun_of_same_bytes_recognizes_once(store):
    from app.review.service import execute

    import pathlib

    data = (pathlib.Path(__file__).resolve().parents[1] / "sample_data" / "ready.csv").read_bytes()
    first = execute(store, data)
    second = execute(store, data)
    assert first["id"] == second["id"]
    assert first["report"]["revenue"] == second["report"]["revenue"]
    assert len(store.list()) == 1


def test_duplicate_replay_is_not_double_counted():
    data = csv_data(
        rows(
            ("M1", "opening", 0, 100, 0),
            ("M2", "change", 40, 140, 1),
            ("M2", "change", 40, 140, 1),  # 同源重放
            ("M3", "close", 100, 140, 0),
        )
    )
    result = inspect(data)
    assert result["accepted"] == 3
    rev = run(data, 3)["cases"][0]["revenue"]
    assert rev["recognized_numerator"] == 100 * 100 + 40 * 60
