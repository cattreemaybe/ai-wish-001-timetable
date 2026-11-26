"""Plain-language preflight checks for non-technical timetable staff."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .analysis import analyze_scenario
from .builder import PlanBuilder, PlanningError
from .domain import Scenario, SUBJECTS, LANGUAGES

RESOURCE_CODES = {
    "capacity_conflict", "teacher_capacity", "teacher_availability",
    "walk_cap_teacher_conflict", "room_conflict",
}
def _required_subjects(scenario: Scenario) -> list[str]:
    if not scenario.students:
        return ["语文", "数学", "英语", "日语", *SUBJECTS[4:]]
    required = {"语文", "数学"}
    for s in scenario.students:
        required.add(s.language)
        required.add(s.first_subject)
        required.update(s.second_subjects)
    return sorted(required)


def _item(key: str, label: str, status: str, value: str, detail: str, link: str) -> dict[str, Any]:
    return {"key": key, "label": label, "status": status, "value": value, "detail": detail, "link": link}


def preflight_scenario(scenario: Scenario) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    blocking: list[str] = []
    warnings: list[str] = []
    resource_shortage = False
    analysis = analyze_scenario(scenario)

    # 1. Students
    students = scenario.students
    if not students:
        items.append(_item("students", "学生与选科", "error", "0 人",
                           "还没有学生数据。请下载模板导入，或手动新增学生。", "/students"))
        blocking.append("缺少学生数据")
    else:
        bad = 0
        for s in students:
            if s.language not in LANGUAGES or s.first_subject not in ("物理", "历史") or len(set(s.second_subjects)) != 2:
                bad += 1
        status = "warn" if bad else "ok"
        detail = f"{len(scenario.admin_classes())} 个行政班，{analysis['combination_count']} 种选科组合"
        if bad:
            detail += f"；{bad} 名学生选科信息不完整"
            blocking.append(f"{bad} 名学生选科信息不完整")
        items.append(_item("students", "学生与选科", status, f"{len(students)} 人", detail, "/students"))

    # 2. Teachers
    required_subjects = _required_subjects(scenario)
    teacher_counts = Counter(t.subject for t in scenario.teachers)
    if not scenario.teachers:
        items.append(_item("teachers", "教师与任课", "error", "0 人",
                           "还没有教师数据。请导入教师名单或手动新增。", "/teachers"))
        blocking.append("缺少教师数据")
    else:
        missing = [s for s in required_subjects if teacher_counts.get(s, 0) == 0]
        status = "error" if missing else "ok"
        detail = "、".join(f"{s}{teacher_counts.get(s, 0)}人" for s in SUBJECTS if teacher_counts.get(s))
        if missing:
            detail = f"缺少 {('、'.join(missing))} 教师；{detail}"
            blocking.append(f"缺少 {('、'.join(missing))} 教师")
        items.append(_item("teachers", "教师与任课", status, f"{len(scenario.teachers)} 人", detail, "/teachers"))

    # 3. Rooms
    if not scenario.rooms:
        items.append(_item("rooms", "教室资源", "error", "0 间",
                           "还没有教室数据。请导入教室清单或手动新增。", "/rooms"))
        blocking.append("缺少教室数据")
    else:
        max_room = max(r.capacity for r in scenario.rooms)
        max_class = max((len([s for s in students if s.admin_class == ac]) for ac in scenario.admin_classes()), default=0)
        status = "ok"
        detail = f"{len(scenario.rooms)} 间，最大 {max_room} 座"
        if max_room < 30:
            status = "error"
            detail += "；没有适合教学班的教室"
            blocking.append("教室容量不足")
        elif max_class > max_room:
            status = "warn"
            detail += f"；最大行政班 {max_class} 人超过最大教室"
            warnings.append("部分行政班人数超过最大教室容量")
        items.append(_item("rooms", "教室资源", status, f"{len(scenario.rooms)} 间", detail, "/rooms"))

    # 4. Courses
    course_errors = []
    for subject in required_subjects:
        if not scenario.course_config.get(subject):
            course_errors.append(f"未配置{subject}")
    totals = [sum(scenario.required_hours(s).values()) for s in students] if students else []
    if totals and any(total != 31 for total in totals):
        course_errors.append(f"每生课时应为31节，当前为{min(totals)}-{max(totals)}节")
    status = "error" if course_errors else "ok"
    detail = "每生每周31节" if not course_errors else "；".join(course_errors[:3])
    if course_errors:
        blocking.extend(course_errors)
    items.append(_item("courses", "课程与课时", status, "31 节/周" if not course_errors else "待修正",
                       detail, "/courses"))

    # 5. Time model
    active = scenario.active_slots()
    phases = Counter(s.phase for s in active)
    bands = Counter(s.band for s in active if s.phase == "elective")
    time_errors = []
    if len(active) != 31:
        time_errors.append(f"教学时段为{len(active)}节，应为31节")
    if phases.get("base", 0) < 13:
        time_errors.append("基础课时段不足13节")
    if phases.get("foreign", 0) < 6:
        time_errors.append("外语时段不足6节")
    for band in ("first", "second_a", "second_b"):
        if bands.get(band, 0) < 4:
            time_errors.append(f"走班段{band}不足4节")
    status = "error" if time_errors else "ok"
    detail = "42格/31个教学时段" if not time_errors else "；".join(time_errors)
    if time_errors:
        blocking.extend(time_errors)
    items.append(_item("time", "上课时间", status, f"{len(active)} 节", detail, "/time-model"))

    # 6. Rules
    rules = scenario.rules
    hard = [
        "teacher_no_overlap", "student_no_overlap", "room_no_overlap",
        "room_capacity", "prescribed_hours", "teacher_unavailable",
        "forbid_non_teaching_slots", "fixed_component_teacher",
        "max_two_same_subject_per_day", "math_lecture_practice_alternate",
        "physics_only_with_history", "foreign_only_with_foreign",
        "second_choice_max_three_subjects",
    ]
    disabled = [k for k in hard if rules.get(k) is False]
    cap = int(rules.get("walk_group_admin_class_cap") or 0)
    status = "warn" if disabled else "ok"
    detail = "硬约束已启用" + (f"；走班组上限={cap}" if cap else "；走班组上限未启用（待确认）")
    if disabled:
        detail = f"{len(disabled)} 条硬约束未启用；{detail}"
        warnings.append("有硬约束被关闭")
    items.append(_item("rules", "排课规则", status, "已配置", detail, "/rules"))

    # 7. Build-resource check (only when the basics make sense)
    if not blocking:
        try:
            PlanBuilder(scenario).build()
            items.append(_item("resources", "资源可行性", "ok", "预检通过",
                               "教学班、教师和教室可以支撑一次求解。", "/solve"))
        except PlanningError as exc:
            category = "资源不足" if exc.code in RESOURCE_CODES else "配置需要修正"
            if exc.code in RESOURCE_CODES:
                resource_shortage = True
            items.append(_item("resources", "资源可行性", "error", category,
                               exc.message, "/solve"))
            blocking.append(exc.message)
    else:
        items.append(_item("resources", "资源可行性", "pending", "待检查",
                           "先补齐上面的基础数据，再做资源可行性检查。", "/prepare"))

    errors = [i for i in items if i["status"] == "error"]
    ready = not errors
    if not students or not scenario.teachers or not scenario.rooms:
        status_text = "请先完成基础数据准备"
    elif resource_shortage:
        status_text = "教师或教室资源不足，暂时无法排课"
    elif not ready:
        status_text = "还有配置需要修正"
    elif warnings:
        status_text = "可以排课，但有风险提示"
    else:
        status_text = "配置完整，可以自动排课"
    return {
        "ready": ready,
        "status": "ready" if ready and not warnings else "warning" if ready else "blocked",
        "message": status_text,
        "items": items,
        "blocking": blocking,
        "warnings": warnings,
        "analysis": {
            "students": len(students),
            "teachers": len(scenario.teachers),
            "rooms": len(scenario.rooms),
            "combinations": analysis["combination_count"],
            "capacity_warnings": analysis["capacity_warnings"],
        },
    }
