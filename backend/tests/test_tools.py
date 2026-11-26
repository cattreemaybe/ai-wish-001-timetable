from __future__ import annotations

from aiwish.data_gen import build_all_scenarios
from aiwish.tools import (
    analyze_selection, describe_tools, diagnose_conflicts, export_timetable,
    get_rules, get_schedule, reschedule_partial, run_auto_schedule, update_rules,
)


def test_tool_surface():
    info = describe_tools()
    names = {t["name"] for t in info["tools"]}
    assert {"import_basic_data", "analyze_selection", "get_rules", "update_rules",
            "run_auto_schedule", "get_schedule", "diagnose_conflicts",
            "reschedule_partial", "export_timetable"} <= names
    assert "本机" in info["privacy"]


def test_rule_change_requires_confirmation():
    sc = build_all_scenarios()["A"]
    proposal = update_rules(sc, {"walk_group_admin_class_cap": 2})
    assert proposal["ok"] is False
    assert proposal["requires_confirmation"] is True
    applied = update_rules(sc, {"walk_group_admin_class_cap": 2}, confirmed=True)
    assert applied["ok"] is True
    assert applied["scenario"]["rules"]["walk_group_admin_class_cap"] == 2
    bad = update_rules(sc, {"walk_group_admin_class_cap": 1})
    assert bad["ok"] is False
    assert any("0或" in e for e in bad["errors"])


def test_analysis_and_schedule_tools():
    sc = build_all_scenarios()["A"]
    analysis = analyze_selection(sc)
    assert analysis["student_count"] == 40
    result = run_auto_schedule(sc, time_limit_seconds=10)
    assert result["status"] == "solved"
    schedule = get_schedule(sc, result)
    assert schedule["validation"]["passed"]
    diag = diagnose_conflicts(sc, result)
    assert diag["passed"] is True
    export = export_timetable(result, "student")
    assert len(export["entries"]) == len(result["tasks"])
    assert reschedule_partial()["supported"] is False
    rules = get_rules(sc)
    assert rules["rules"]["teacher_no_overlap"] is True
