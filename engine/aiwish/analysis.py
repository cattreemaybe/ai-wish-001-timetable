"""Student-choice and resource analysis, independent of the web layer."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .domain import SECOND_SUBJECTS, Scenario


def _time_summary(doc: dict[str, Any]) -> dict[str, Any]:
    slots = doc.get("time_model", {}).get("slots", [])
    active = [s for s in slots if s.get("active")]
    by_phase = Counter(s.get("phase") for s in active)
    return {
        "active_slots": len(active),
        "grid_slots": len(slots),
        "phases": dict(by_phase),
        "assumption": doc.get("time_model", {}).get("assumption", ""),
    }


def analyze_doc(doc: dict[str, Any]) -> dict[str, Any]:
    students = doc.get("students", [])
    teachers = doc.get("teachers", [])
    rooms = doc.get("rooms", [])
    admin_sizes = Counter(s["admin_class"] for s in students)
    first = Counter(s["first_subject"] for s in students)
    second = Counter(x for s in students for x in s["second_subjects"])
    languages = Counter(s["language"] for s in students)
    combos = Counter(
        (s["language"], s["first_subject"], s["second_subjects"][0], s["second_subjects"][1])
        for s in students
    )
    teacher_counts = Counter(t["subject"] for t in teachers)
    estimate = {}
    for sub in ("物理", "历史", *SECOND_SUBJECTS):
        enrolled = first.get(sub, 0) if sub in ("物理", "历史") else second.get(sub, 0)
        teachers_n = teacher_counts.get(sub, 0)
        estimate[sub] = {
            "enrollment": enrolled,
            "teachers": teachers_n,
            "sections_at_60": max(0, -(-enrolled // 60)) if enrolled else 0,
        }
    warnings = []
    for sub, e in estimate.items():
        if e["sections_at_60"] > e["teachers"] and e["enrollment"]:
            warnings.append(
                f"{sub} 在 60 人教室上限下至少需要 {e['sections_at_60']} 个教学班，"
                f"但只有 {e['teachers']} 名教师；若同一走班时段全部并行，可能无解。"
            )
    return {
        "student_count": len(students),
        "teacher_count": len(teachers),
        "room_count": len(rooms),
        "admin_class_count": len(admin_sizes),
        "admin_class_sizes": dict(sorted(admin_sizes.items())),
        "first_subject_counts": dict(first),
        "second_subject_counts": dict(second),
        "language_counts": dict(languages),
        "combination_count": len(combos),
        "combinations": [
            {"language": k[0], "first": k[1], "seconds": [k[2], k[3]], "count": v}
            for k, v in sorted(combos.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "teacher_counts": dict(teacher_counts),
        "elective_capacity_estimate": estimate,
        "capacity_warnings": warnings,
        "time_model_summary": _time_summary(doc),
    }


def analyze_scenario(scenario: Scenario) -> dict[str, Any]:
    return analyze_doc(scenario.to_dict())
