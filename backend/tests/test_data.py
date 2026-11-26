from __future__ import annotations

from collections import Counter

from aiwish.builder import PlanBuilder
from aiwish.data_gen import build_all_scenarios


def test_fixed_data_and_all_combinations(scenarios):
    f = scenarios["F"]
    assert len(f.students) == 320
    assert len(f.teachers) == 62
    combos = {
        (s.language, s.first_subject, tuple(s.second_subjects)) for s in f.students
    }
    assert len(combos) == 24
    assert len(f.admin_classes()) == 8
    assert len(f.active_slots()) == 31


def test_reproducible_generation():
    a = build_all_scenarios()["F"].to_dict()
    b = build_all_scenarios()["F"].to_dict()
    assert a["students"] == b["students"]
    assert a["teachers"] == b["teachers"]


def test_each_student_has_31_weekly_hours(scenarios):
    for scenario in scenarios.values():
        for student in scenario.students[:10]:
            assert sum(scenario.required_hours(student).values()) == 31


def test_a_is_single_combo_and_b_has_two(scenarios):
    assert len({(s.first_subject, tuple(s.second_subjects)) for s in scenarios["A"].students}) == 1
    assert len({(s.first_subject, tuple(s.second_subjects)) for s in scenarios["B"].students}) == 2


def test_builder_task_counts_and_walking(scenarios):
    for key in ("A", "B", "C", "D", "E", "F"):
        plan = PlanBuilder(scenarios[key]).build()
        counts = Counter()
        for task in plan.tasks:
            for sid in task.student_ids:
                counts[sid] += 1
        assert all(v == 31 for v in counts.values()), key
        # Three walking bands, each exactly four slots.
        assert {t.band for t in plan.tasks if t.phase == "elective"} == {"first", "second_a", "second_b"}


def test_second_choice_never_four_subjects(scenarios):
    plan = PlanBuilder(scenarios["D"]).build()
    bands = {}
    for task in plan.tasks:
        if task.phase == "elective" and task.band in ("second_a", "second_b"):
            bands.setdefault((task.band, task.allowed_slots[0]), set()).add(task.subject)
    for subjects in bands.values():
        assert len(subjects) <= 3


def test_languages_are_split_into_separate_classes(scenarios):
    plan = PlanBuilder(scenarios["E"]).build()
    foreign = [c for c in plan.classes if c.kind == "foreign"]
    assert {c.subject for c in foreign} == {"英语", "日语"}
