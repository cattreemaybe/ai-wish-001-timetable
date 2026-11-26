from __future__ import annotations

import copy

from aiwish.validator import validate_schedule


def test_validator_passes_valid_result(scenarios, solved_a):
    report = validate_schedule(scenarios["A"], solved_a["classes"], solved_a["tasks"])
    assert report["passed"]
    assert report["summary"]["hard_constraint_violations"] == 0


def test_validator_detects_student_and_room_conflict(scenarios, solved_a):
    classes = copy.deepcopy(solved_a["classes"])
    tasks = copy.deepcopy(solved_a["tasks"])
    # Force two tasks of the same admin class into the same slot.
    a = tasks[0]
    b = next(t for t in tasks[1:] if t["class_id"] == a["class_id"])
    b.update({
        "slot_label": a["slot_label"], "slot_index": a["slot_index"],
        "day": a["day"], "day_index": a["day_index"], "period": a["period"],
    })
    report = validate_schedule(scenarios["A"], classes, tasks)
    assert not report["passed"]
    assert report["summary"]["student_time_conflicts"] > 0
    assert report["summary"]["room_time_conflicts"] > 0


def test_validator_detects_missing_student_hours(scenarios, solved_a):
    classes = copy.deepcopy(solved_a["classes"])
    tasks = copy.deepcopy(solved_a["tasks"])
    sid = scenarios["A"].students[0].id
    before = sum(1 for t in tasks for x in t["student_ids"] if x == sid)
    victim = next(t for t in tasks if sid in t["student_ids"])
    victim["student_ids"] = [x for x in victim["student_ids"] if x != sid]
    after = sum(1 for t in tasks for x in t["student_ids"] if x == sid)
    assert after == before - 1
    report = validate_schedule(scenarios["A"], classes, tasks)
    assert not report["passed"]
    assert report["summary"]["student_missing_hours"] > 0


def test_validator_detects_room_capacity(scenarios, solved_a):
    classes = copy.deepcopy(solved_a["classes"])
    tasks = copy.deepcopy(solved_a["tasks"])
    # A 100-student claim in an existing 45-seat room.
    tasks[0]["student_ids"] = [f"FAKE{i}" for i in range(100)]
    report = validate_schedule(scenarios["A"], classes, tasks)
    assert not report["passed"]
    assert report["summary"]["room_capacity_violations"] > 0


def test_validator_detects_phase_mismatch(scenarios, solved_a):
    classes = copy.deepcopy(solved_a["classes"])
    tasks = copy.deepcopy(solved_a["tasks"])
    tasks[0]["phase"] = "foreign"
    report = validate_schedule(scenarios["A"], classes, tasks)
    assert not report["passed"]
    assert report["summary"]["invalid_slots"] > 0
