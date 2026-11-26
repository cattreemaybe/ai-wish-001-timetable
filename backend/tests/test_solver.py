from __future__ import annotations

import pytest

from aiwish.builder import PlanBuilder
from aiwish.domain import STATUS_ZH
from aiwish.runner import run_scenario
from aiwish.solver import SolveOptions, solve_plan
from aiwish.validator import validate_schedule


@pytest.mark.parametrize("key", ["A", "B", "C", "D", "E", "F"])
def test_scenarios_solve_and_validate(scenarios, key):
    result = run_scenario(scenarios[key], time_limit_seconds=20)
    assert result["status"] == "solved", (key, result["message"])
    assert result["solver_status"] in ("OPTIMAL", "FEASIBLE")
    assert result["validation"]["passed"], result["validation"]["violations"][:5]
    s = result["validation"]["summary"]
    for field in (
        "student_time_conflicts", "teacher_time_conflicts", "room_time_conflicts",
        "student_missing_hours", "room_capacity_violations",
        "teacher_unavailable_violations", "daily_limit_violations",
        "math_alternation_violations", "walk_rule_violations",
        "view_inconsistencies", "invalid_slots",
    ):
        assert s[field] == 0, (key, field, s[field])
    assert set(result["metrics"]["elective_band_subjects"]) == {"first", "second_a", "second_b"}


def test_f_metrics(solved_f):
    assert solved_f["status"] == "solved"
    m = solved_f["metrics"]
    assert m["student_count"] == 320
    assert m["teaching_class_count"] == len(solved_f["classes"])
    assert m["walking_student_count"] == 320
    assert m["student_walk_transitions"] == 640
    assert m["merged_class_count"] > 0
    assert m["scheduled_slots"] == 31
    assert m["weekly_task_count"] == len(solved_f["tasks"])
    assert solved_f["solve_seconds"] >= 0


def test_a_has_no_real_walking(solved_a):
    assert solved_a["metrics"]["walking_student_count"] == 0
    assert solved_a["metrics"]["student_walk_transitions"] == 0


def test_g_is_proven_infeasible_before_solver(scenarios):
    result = run_scenario(scenarios["G"], time_limit_seconds=10)
    assert result["status"] == "infeasible"
    assert result["solver_status"] == "PRECHECK_INFEASIBLE"
    assert result["solver_status"] != "UNKNOWN"
    assert "无解" in result["message"]
    assert result["tasks"] == []
    assert result["validation"] is None
    assert result["precheck"]["code"] == "capacity_conflict"


def test_strict_walk_cap_is_infeasible_on_f(scenarios):
    from copy import deepcopy
    sc = deepcopy(scenarios["F"])
    sc.rules["walk_group_admin_class_cap"] = 2
    result = run_scenario(sc, time_limit_seconds=10)
    assert result["status"] == "infeasible"
    assert result["solver_status"] == "PRECHECK_INFEASIBLE"
    assert result["precheck"]["code"] == "walk_cap_teacher_conflict"


def test_math_sequence_alternates(scenarios):
    plan = PlanBuilder(scenarios["F"]).build()
    result = solve_plan(plan, SolveOptions(time_limit_seconds=20, num_workers=4))
    assert result["status"] == "solved"
    for admin in scenarios["F"].admin_classes():
        tasks = [t for t in result["tasks"] if t["subject"] == "数学" and admin in t["admin_classes"]]
        tasks.sort(key=lambda t: t["slot_index"])
        assert [t["kind"] for t in tasks] == ["lecture", "practice"] * 4


def test_teacher_binding_is_honoured(scenarios):
    from copy import deepcopy
    from aiwish.runner import run_scenario
    sc = deepcopy(scenarios["A"])
    sc.teacher_bindings["语文|高一(1)班"] = "T-CN-03"
    sc.teacher_bindings["数学|高一(1)班"] = "T-MA-02"
    result = run_scenario(sc, time_limit_seconds=10)
    assert result["status"] == "solved"
    cn = next(c for c in result["classes"] if c["name"] == "语文·高一(1)班")
    ma = next(c for c in result["classes"] if c["name"] == "数学·高一(1)班")
    assert cn["teacher_id"] == "T-CN-03"
    assert ma["teacher_id"] == "T-MA-02"
    assert result["validation"]["passed"]


def test_teacher_weekly_max_is_hard(scenarios):
    from copy import deepcopy
    from aiwish.runner import run_scenario
    sc = deepcopy(scenarios["A"])
    sc.teacher_bindings["数学|高一(1)班"] = "T-MA-02"
    next(t for t in sc.teachers if t.id == "T-MA-02").max_weekly_periods = 1
    result = run_scenario(sc, time_limit_seconds=10)
    assert result["status"] == "infeasible"
    assert result["solver_status"] == "INFEASIBLE"
    assert result["tasks"] == []
