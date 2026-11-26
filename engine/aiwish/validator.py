"""Independent timetable validator.

This module deliberately does NOT import the solver or builder.  It consumes the
scenario, the built teaching-class metadata and a solved list of lesson tasks,
then re-checks every acceptance criterion from scratch.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .domain import (
    Scenario, SECOND_SUBJECTS, FIRST_SUBJECTS, LANGUAGES,
)


def validate_schedule(
    scenario: Scenario,
    classes: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    slots = scenario.active_slots()
    slot_by_label = {s.label: s for s in slots}
    all_grid_labels = {s["label"] for s in scenario.time_model["slots"]}
    students = {s.id: s for s in scenario.students}
    teachers = {t.id: t for t in scenario.teachers}
    rooms = {r.id: r for r in scenario.rooms}
    class_by_id = {c["id"]: c for c in classes}
    task_by_id = {t["id"]: t for t in tasks}

    violations: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    warnings: list[str] = []

    def add(code: str, category: str, scope: str, message: str) -> None:
        counts[code] += 1
        if len(violations) < 300:
            violations.append({
                "code": code, "category": category,
                "scope": scope, "message": message,
            })

    # ------------------------------------------------------------------ shape
    if len(task_by_id) != len(tasks):
        add("duplicate_task", "structure", "tasks", "任务编号重复")
    for cid, cls in class_by_id.items():
        missing = [tid for tid in cls.get("task_ids", []) if tid not in task_by_id]
        if missing:
            add("missing_task", "structure", cid,
                f"教学班 {cls.get('name')} 缺少任务: {missing[:5]}")
        for tid in cls.get("task_ids", []):
            task = task_by_id.get(tid)
            if task and task.get("class_id") != cid:
                add("task_class_mismatch", "structure", tid,
                    f"任务 {tid} 的 class_id 与教学班不一致")

    # Every task must be placed in an active teaching slot and must be allowed
    # by its own allowed_slots list.
    for task in tasks:
        label = task.get("slot_label")
        if label not in slot_by_label:
            add("invalid_slot", "time", task["id"],
                f"任务 {task['id']} 使用了非教学时段/非法时段: {label}")
            continue
        slot = slot_by_label[label]
        if label not in (task.get("allowed_slots") or []):
            add("slot_not_allowed", "time", task["id"],
                f"任务 {task['id']} 被安排到其允许集合之外的时段 {label}")
        if task.get("phase") != slot.phase or task.get("band") != slot.band:
            add("phase_mismatch", "time", task["id"],
                f"任务 {task['id']} 的阶段/走班段与时段不一致："
                f"任务({task.get('phase')}/{task.get('band')}) vs {label}({slot.phase}/{slot.band})")
        room = rooms.get(task.get("room_id"))
        if room is None:
            add("room_missing", "room", task["id"],
                f"任务 {task['id']} 的教室不存在: {task.get('room_id')}")
        teacher = teachers.get(task.get("teacher_id"))
        if teacher is None:
            add("teacher_missing", "teacher", task["id"],
                f"任务 {task['id']} 的教师不存在: {task.get('teacher_id')}")
        elif task.get("subject") not in (teacher.candidate_subjects or [teacher.subject]):
            add("teacher_subject_mismatch", "teacher", task["id"],
                f"教师 {teacher.name} 不是 {task.get('subject')} 候选教师")
        for sid in task.get("student_ids", []):
            if sid not in students:
                add("student_missing", "structure", task["id"],
                    f"任务 {task['id']} 含不存在的学生 {sid}")

    # ------------------------------------------------------------------ classes
    for cid, cls in class_by_id.items():
        size = len(cls.get("student_ids", []))
        room = rooms.get(cls.get("room_id"))
        if room and size > room.capacity:
            add("room_capacity", "room", cid,
                f"{cls.get('name')} 有{size}人，超过教室{room.name}({room.capacity}座)")
        teacher = teachers.get(cls.get("teacher_id"))
        if teacher is None:
            add("class_teacher_missing", "teacher", cid,
                f"教学班 {cls.get('name')} 的教师不存在")
        if len(cls.get("task_ids", [])) != int(cls.get("required_hours", 0)):
            add("class_task_count", "structure", cid,
                f"教学班 {cls.get('name')} 任务数 {len(cls.get('task_ids', []))} "
                f"与周课时 {cls.get('required_hours')} 不一致")
        # Same teaching class + same component must keep one fixed teacher.
        comp_teachers: dict[str, set[str]] = defaultdict(set)
        for tid in cls.get("task_ids", []):
            task = task_by_id.get(tid)
            if task:
                comp_teachers[task["component"]].add(task["teacher_id"])
        for comp, tids in comp_teachers.items():
            if len(tids) > 1:
                add("component_teacher_changed", "teacher", cid,
                    f"{cls.get('name')} 的细分课程 {comp} 出现多个教师: {sorted(tids)}")

    # Student views and hard checks.
    student_tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        for sid in task.get("student_ids", []):
            student_tasks[sid].append(task)

    required_subject: dict[str, dict[str, int]] = {}
    for sid, student in students.items():
        req = scenario.required_hours(student)
        required_subject[sid] = req
        ts = student_tasks.get(sid, [])
        by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in ts:
            by_slot[t.get("slot_label")].append(t)
        for label, group in by_slot.items():
            if len(group) > 1:
                for _ in range(len(group) - 1):
                    add("student_conflict", "student", sid,
                        f"{student.name} 在 {label} 同时有 {len(group)} 门课")
        for slot in slots:
            if slot.label not in by_slot:
                add("student_missing_slot", "student", sid,
                    f"{student.name} 在 {slot.label} 没有课程")
        subject_count = Counter(t["subject"] for t in ts)
        for subject, need in req.items():
            got = subject_count.get(subject, 0)
            if got != need:
                add("student_hours", "student", sid,
                    f"{student.name} 的{subject}课时为{got}，规定{need}")
        comp_need = scenario.required_component_hours(student)
        comp_got = Counter((t["subject"], t["component"]) for t in ts)
        for key, need in comp_need.items():
            got = comp_got.get(key, 0)
            if got != need:
                add("student_component_hours", "student", sid,
                    f"{student.name} 的{key[0]}·{key[1]}课时为{got}，规定{need}")
        # Daily max two lessons of the same subject.
        day_subject = Counter((t["day_index"], t["subject"]) for t in ts)
        for (day, subject), n in day_subject.items():
            if n > 2:
                add("daily_subject_limit", "student", sid,
                    f"{student.name} 在周{day + 1}的{subject}有{n}节，超过2节")

    # Teacher views.
    teacher_tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        teacher_tasks[task.get("teacher_id")].append(task)
    for tid, ts in teacher_tasks.items():
        teacher = teachers.get(tid)
        if teacher is None:
            continue
        by_slot = Counter(t.get("slot_label") for t in ts)
        for label, n in by_slot.items():
            if n > 1:
                for _ in range(n - 1):
                    add("teacher_conflict", "teacher", tid,
                        f"{teacher.name} 在 {label} 有 {n} 个教学任务")
        unavailable = set(teacher.unavailable_slots)
        for t in ts:
            if t.get("slot_label") in unavailable:
                add("teacher_unavailable", "teacher", tid,
                    f"{teacher.name} 被安排在不可排时间 {t.get('slot_label')}")
        if teacher.max_weekly_periods is not None and len(ts) > teacher.max_weekly_periods:
            add("teacher_weekly_limit", "teacher", tid,
                f"{teacher.name} 周课时{len(ts)}超过上限{teacher.max_weekly_periods}")

    # Room views.
    room_tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        room_tasks[task.get("room_id")].append(task)
    for rid, ts in room_tasks.items():
        by_slot = Counter(t.get("slot_label") for t in ts)
        for label, n in by_slot.items():
            if n > 1:
                for _ in range(n - 1):
                    add("room_conflict", "room", rid,
                        f"教室 {rid} 在 {label} 被安排 {n} 个教学班")
        room = rooms.get(rid)
        if room:
            for t in ts:
                if len(t.get("student_ids", [])) > room.capacity:
                    add("room_capacity", "room", rid,
                        f"教室 {room.name} 容量{room.capacity}，"
                        f"任务 {t['id']} 有{len(t['student_ids'])}人")

    # Math sequence alternation, per admin class.
    for admin in scenario.admin_classes():
        math_tasks = [
            t for t in tasks
            if t["subject"] == "数学" and admin in t.get("admin_classes", [])
        ]
        math_tasks.sort(key=lambda t: slot_by_label.get(t.get("slot_label"), slots[0]).index
                        if t.get("slot_label") in slot_by_label else 999)
        kinds = [t["kind"] for t in math_tasks]
        if len(math_tasks) != 8:
            add("math_count", "rule", admin,
                f"{admin} 的数学任务数为{len(math_tasks)}，应为8")
        if any(a == b for a, b in zip(kinds, kinds[1:])):
            add("math_not_alternating", "rule", admin,
                f"{admin} 的数学课未按正课/落实课交替: {kinds}")
        if kinds and kinds[0] != "lecture":
            add("math_start_kind", "rule", admin,
                f"{admin} 的数学周序列未从正课开始: {kinds}")

    # Walking-band rules (structural, checked on the final schedule).
    for slot in slots:
        if slot.band == "first":
            for t in [x for x in tasks if x.get("slot_label") == slot.label]:
                if t["subject"] not in FIRST_SUBJECTS:
                    add("physics_history_walk", "rule", slot.label,
                        f"首选走班时段 {slot.label} 出现非物理/历史课程 {t['subject']}")
        if slot.phase == "foreign":
            for t in [x for x in tasks if x.get("slot_label") == slot.label]:
                if t["subject"] not in LANGUAGES:
                    add("foreign_walk", "rule", slot.label,
                        f"外语时段 {slot.label} 出现非外语课程 {t['subject']}")
        if slot.band in ("second_a", "second_b"):
            subjects = {t["subject"] for t in tasks if t.get("slot_label") == slot.label}
            if len(subjects) > 3:
                add("four_subject_walk", "rule", slot.label,
                    f"{slot.label} 同时出现 {len(subjects)} 门再选科目: {sorted(subjects)}")
            bad = subjects - set(SECOND_SUBJECTS)
            if bad:
                add("second_walk_subject", "rule", slot.label,
                    f"{slot.label} 出现非再选科目: {bad}")
    cap = int(scenario.rules.get("walk_group_admin_class_cap") or 0)
    if cap:
        for cls in classes:
            if cls.get("kind", "").startswith("elective") and len(cls.get("admin_classes", [])) > cap:
                add("walk_group_admin_cap", "rule", cls["id"],
                    f"{cls.get('name')} 跨{len(cls.get('admin_classes', []))}个行政班，"
                    f"超过暂定上限{cap}")
    else:
        warnings.append(
            "走班组最多两个行政班的暂定规则未启用（walk_group_admin_class_cap=0）；"
            "该规则在需求中标注为待确认，启用后会作为硬约束校验。"
        )

    # Derived views must all be consistent with the same task list.
    view_counts = {
        "student_entries": sum(len(t.get("student_ids", [])) for t in tasks),
        "teacher_entries": len(tasks),
        "room_entries": len(tasks),
        "admin_entries": sum(len(t.get("admin_classes", [])) for t in tasks),
    }
    # A task list -> view retrieval round trip.
    for task in tasks:
        tid = task["id"]
        if tid not in class_by_id.get(task.get("class_id"), {}).get("task_ids", []):
            add("view_admin", "view", tid, f"任务 {tid} 未出现在所属教学班的任务列表中")
        for sid in task.get("student_ids", []):
            if tid not in [t["id"] for t in student_tasks.get(sid, [])]:
                add("view_student", "view", tid, f"任务 {tid} 未出现在学生 {sid} 的视图中")
        admin_set = {students[sid].admin_class for sid in task.get("student_ids", []) if sid in students}
        if admin_set != set(task.get("admin_classes", [])):
            add("view_admin_composition", "view", tid,
                f"任务 {tid} 的行政班元数据与学生成员不一致")
        if task.get("room_id") not in room_tasks or tid not in [t["id"] for t in room_tasks[task.get("room_id")]]:
            add("view_room", "view", tid, f"任务 {tid} 未出现在教室视图中")
        if task.get("teacher_id") not in teacher_tasks or tid not in [t["id"] for t in teacher_tasks[task.get("teacher_id")]]:
            add("view_teacher", "view", tid, f"任务 {tid} 未出现在教师视图中")

    # Acceptance counters (explicitly named).
    summary = {
        "student_time_conflicts": counts.get("student_conflict", 0),
        "teacher_time_conflicts": counts.get("teacher_conflict", 0),
        "room_time_conflicts": counts.get("room_conflict", 0),
        "student_missing_hours": (
            counts.get("student_hours", 0) + counts.get("student_component_hours", 0)
        ),
        "room_capacity_violations": counts.get("room_capacity", 0),
        "teacher_unavailable_violations": counts.get("teacher_unavailable", 0),
        "daily_limit_violations": counts.get("daily_subject_limit", 0),
        "math_alternation_violations": (
            counts.get("math_not_alternating", 0) + counts.get("math_count", 0)
            + counts.get("math_start_kind", 0)
        ),
        "walk_rule_violations": (
            counts.get("physics_history_walk", 0) + counts.get("foreign_walk", 0)
            + counts.get("four_subject_walk", 0) + counts.get("second_walk_subject", 0)
            + counts.get("walk_group_admin_cap", 0)
        ),
        "view_inconsistencies": sum(v for k, v in counts.items() if k.startswith("view_")),
        "invalid_slots": counts.get("invalid_slot", 0) + counts.get("slot_not_allowed", 0)
                          + counts.get("phase_mismatch", 0),
        "hard_constraint_violations": sum(
            v for k, v in counts.items()
            if k not in ("student_missing_slot",)
        ),
    }
    # Missing slots are a hard failure too (student must have no free periods in
    # this 31-slot / 31-hour model).
    summary["student_missing_hours"] += counts.get("student_missing_slot", 0)
    summary["hard_constraint_violations"] += counts.get("student_missing_slot", 0)
    summary["passed"] = summary["hard_constraint_violations"] == 0
    return {
        "passed": summary["passed"],
        "summary": summary,
        "violation_counts": dict(sorted(counts.items())),
        "violations": violations,
        "warnings": warnings,
        "checked": {
            "tasks": len(tasks),
            "classes": len(classes),
            "students": len(students),
            "teachers": len(teachers),
            "rooms": len(rooms),
            "active_slots": len(slots),
        },
        "view_counts": view_counts,
    }
