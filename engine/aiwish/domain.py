"""Domain model for the AI-WISH-001 timetabling engine.

The engine is intentionally independent from FastAPI, SQLite, React and any DSH
plugin code.  Everything in this module is plain Python and JSON-serialisable.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

LANGUAGES = ["英语", "日语"]
FIRST_SUBJECTS = ["物理", "历史"]
SECOND_SUBJECTS = ["生物", "化学", "地理", "政治"]
# This order drives the two-subject walking bands.  It guarantees that at most
# three distinct second-choice subjects run in one band (never four).
SECOND_SUBJECT_ORDER = ["生物", "化学", "地理", "政治"]
SUBJECTS = ["语文", "数学", "英语", "日语", "物理", "历史", "生物", "化学", "地理", "政治"]

SUBJECT_SHORT = {
    "语文": "语", "数学": "数", "英语": "英", "日语": "日",
    "物理": "物", "历史": "史", "生物": "生", "化学": "化",
    "地理": "地", "政治": "政",
}

DEFAULT_COURSE_CONFIG: dict[str, list[dict[str, Any]]] = {
    "语文": [
        {"name": "正课", "hours": 3, "kind": "lecture"},
        {"name": "落实课", "hours": 1, "kind": "practice"},
        {"name": "语言专题", "hours": 1, "kind": "seminar"},
    ],
    "数学": [
        {"name": "正课", "hours": 4, "kind": "lecture"},
        {"name": "落实课", "hours": 4, "kind": "practice"},
    ],
    "英语": [
        {"name": "正课", "hours": 3, "kind": "lecture"},
        {"name": "语法", "hours": 1, "kind": "seminar"},
        {"name": "落实课", "hours": 2, "kind": "practice"},
    ],
    "日语": [
        {"name": "正课", "hours": 4, "kind": "lecture"},
        {"name": "落实课", "hours": 2, "kind": "practice"},
    ],
    "物理": [
        {"name": "正课", "hours": 2, "kind": "lecture"},
        {"name": "落实课", "hours": 2, "kind": "practice"},
    ],
    "历史": [
        {"name": "正课", "hours": 2, "kind": "lecture"},
        {"name": "落实课", "hours": 2, "kind": "practice"},
    ],
    "生物": [
        {"name": "正课", "hours": 2, "kind": "lecture"},
        {"name": "落实课", "hours": 2, "kind": "practice"},
    ],
    "化学": [
        {"name": "正课", "hours": 2, "kind": "lecture"},
        {"name": "落实课", "hours": 2, "kind": "practice"},
    ],
    "地理": [
        {"name": "正课", "hours": 2, "kind": "lecture"},
        {"name": "落实课", "hours": 2, "kind": "practice"},
    ],
    "政治": [
        {"name": "正课", "hours": 2, "kind": "lecture"},
        {"name": "落实课", "hours": 2, "kind": "practice"},
    ],
}

DEFAULT_RULES: dict[str, Any] = {
    # Hard constraints that are confirmed by the source request.
    "teacher_no_overlap": True,
    "student_no_overlap": True,
    "room_no_overlap": True,
    "room_capacity": True,
    "prescribed_hours": True,
    "teacher_unavailable": True,
    "forbid_non_teaching_slots": True,
    "fixed_component_teacher": True,
    "max_two_same_subject_per_day": True,
    "math_lecture_practice_alternate": True,
    "physics_only_with_history": True,
    "foreign_only_with_foreign": True,
    "second_choice_max_three_subjects": True,
    # Explicitly tentative in the source request.  The default model keeps the
    # rule visible but does not impose the 2-admin-class cap because it is
    # incompatible with the supplied teacher counts in the comprehensive
    # scenario.  See ASSUMPTIONS.md and TEST_REPORT.md for the measured proof.
    "walk_group_admin_class_cap": 0,  # 0 = off / pending confirmation, 2 = tentative
    "enabled_hard_constraints": [
        "teacher_no_overlap", "student_no_overlap", "room_no_overlap",
        "room_capacity", "prescribed_hours", "teacher_unavailable",
        "forbid_non_teaching_slots", "fixed_component_teacher",
        "max_two_same_subject_per_day", "math_lecture_practice_alternate",
        "physics_only_with_history", "foreign_only_with_foreign",
        "second_choice_max_three_subjects",
    ],
    "weights": {
        "lecture_before_practice": 3,
        "teacher_idle": 1,
        "student_walk": 1,
        "merge_small_classes": 1,
        "minimize_teaching_classes": 1,
        "prefer_two_subject_walk": 1,
    },
    "time_limit_seconds": 30,
    "random_seed": 20261125,
    "num_workers": 8,
}

STATUS_ZH = {
    "OPTIMAL": "已找到最优解",
    "FEASIBLE": "已找到可行解",
    "INFEASIBLE": "已证明无解",
    "UNKNOWN": "超时且未找到可行解",
    "MODEL_INVALID": "模型或数据错误",
    "PRECHECK_INFEASIBLE": "数据预检证明无解",
}


@dataclass
class TimeSlot:
    index: int          # active-slot order used by the solver, -1 if inactive
    day_index: int      # 0=周一 ... 6=周日
    day: str
    period: int
    label: str
    active: bool
    activity: str       # 上课 / 自习 / 周测 / 放假
    phase: str | None = None       # base / foreign / elective
    band: str | None = None        # base / foreign / first / second_a / second_b

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_TIME_MODEL: dict[str, Any] = {
    "name": "默认新高考周课表（31个教学时段）",
    "days": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    "periods_per_day": 6,
    "assumption": (
        "周一至周五第6节自习；周六第5节周测、第6节放假；"
        "周日第1-4节放假、第5-6节上课。31个可排教学时段。"
    ),
    "slots": [],  # filled by build_default_time_slots
}


def build_default_time_slots() -> list[TimeSlot]:
    """Build the 42-cell week grid and its 31 active teaching slots.

    Phase / band assignment is part of the time model and can be changed in
    data, which makes the block structure configurable without touching the
    solver.
    """
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    slots: list[TimeSlot] = []
    active_index = 0
    # First-choice band: Mon/Tue P1-P2. Second band A: Wed/Thu P1-P2.
    # Second band B: Fri P1-P2 + Sat P1-P2.
    elective_band_by_day = {
        0: "first", 1: "first",
        2: "second_a", 3: "second_a",
        4: "second_b", 5: "second_b",
    }
    for d, day in enumerate(days):
        for p in range(1, 7):
            if d <= 4:
                if p <= 2:
                    active, activity = True, "上课"
                    phase, band = "elective", elective_band_by_day[d]
                elif p == 3:
                    active, activity = True, "上课"
                    phase, band = "foreign", "foreign"
                elif p <= 5:
                    active, activity = True, "上课"
                    phase, band = "base", "base"
                else:
                    active, activity = False, "自习"
                    phase, band = None, None
            elif d == 5:  # Saturday
                if p <= 2:
                    active, activity = True, "上课"
                    phase, band = "elective", "second_b"
                elif p == 3:
                    active, activity = True, "上课"
                    phase, band = "foreign", "foreign"
                elif p == 4:
                    active, activity = True, "上课"
                    phase, band = "base", "base"
                elif p == 5:
                    active, activity = False, "周测"
                    phase, band = None, None
                else:
                    active, activity = False, "放假"
                    phase, band = None, None
            else:  # Sunday
                if p <= 4:
                    active, activity = False, "放假"
                    phase, band = None, None
                else:
                    active, activity = True, "上课"
                    phase, band = "base", "base"
            if active:
                idx = active_index
                active_index += 1
            else:
                idx = -1
            slots.append(TimeSlot(
                index=idx, day_index=d, day=day, period=p,
                label=f"{day}第{p}节", active=active, activity=activity,
                phase=phase, band=band,
            ))
    return slots


def default_time_model() -> dict[str, Any]:
    model = dict(DEFAULT_TIME_MODEL)
    model["slots"] = [s.to_dict() for s in build_default_time_slots()]
    return model


@dataclass
class Student:
    id: str
    name: str
    admin_class: str
    language: str
    first_subject: str
    second_subjects: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Student":
        return Student(
            id=d["id"], name=d["name"], admin_class=d["admin_class"],
            language=d["language"], first_subject=d["first_subject"],
            second_subjects=list(d["second_subjects"]),
        )


@dataclass
class Teacher:
    id: str
    name: str
    subject: str
    unavailable_slots: list[str] = field(default_factory=list)
    candidate_subjects: list[str] = field(default_factory=list)
    max_weekly_periods: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Teacher":
        return Teacher(
            id=d["id"], name=d["name"], subject=d["subject"],
            unavailable_slots=list(d.get("unavailable_slots", [])),
            candidate_subjects=list(d.get("candidate_subjects", [d["subject"]])),
            max_weekly_periods=d.get("max_weekly_periods"),
        )


@dataclass
class Room:
    id: str
    name: str
    capacity: int
    building: str = "教学楼"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Room":
        return Room(id=d["id"], name=d["name"], capacity=int(d["capacity"]),
                    building=d.get("building", "教学楼"))


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    seed: int
    time_model: dict[str, Any]
    course_config: dict[str, list[dict[str, Any]]]
    students: list[Student]
    teachers: list[Teacher]
    rooms: list[Room]
    rules: dict[str, Any]
    notes: str = ""
    assumption_tags: list[str] = field(default_factory=list)
    teacher_bindings: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "seed": self.seed, "time_model": self.time_model,
            "course_config": self.course_config,
            "students": [s.to_dict() for s in self.students],
            "teachers": [t.to_dict() for t in self.teachers],
            "rooms": [r.to_dict() for r in self.rooms],
            "rules": self.rules, "notes": self.notes,
            "assumption_tags": self.assumption_tags,
            "teacher_bindings": self.teacher_bindings,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Scenario":
        return Scenario(
            id=d["id"], name=d["name"], description=d["description"],
            seed=int(d["seed"]),
            time_model=d.get("time_model") or default_time_model(),
            course_config=d.get("course_config") or DEFAULT_COURSE_CONFIG,
            students=[Student.from_dict(x) for x in d["students"]],
            teachers=[Teacher.from_dict(x) for x in d["teachers"]],
            rooms=[Room.from_dict(x) for x in d["rooms"]],
            rules={**DEFAULT_RULES, **(d.get("rules") or {})},
            notes=d.get("notes", ""),
            assumption_tags=list(d.get("assumption_tags", [])),
            teacher_bindings=dict(d.get("teacher_bindings") or {}),
        )

    def active_slots(self) -> list[TimeSlot]:
        return [TimeSlot(**s) for s in self.time_model["slots"] if s.get("active")]

    def admin_classes(self) -> list[str]:
        seen: list[str] = []
        for s in self.students:
            if s.admin_class not in seen:
                seen.append(s.admin_class)
        return seen

    def students_by_admin_class(self) -> dict[str, list[Student]]:
        out: dict[str, list[Student]] = {}
        for s in self.students:
            out.setdefault(s.admin_class, []).append(s)
        return out

    def required_hours(self, student: Student) -> dict[str, int]:
        """Return required weekly hours by subject for one student."""
        req: dict[str, int] = {
            "语文": _subject_hours(self.course_config, "语文"),
            "数学": _subject_hours(self.course_config, "数学"),
            student.language: _subject_hours(self.course_config, student.language),
            student.first_subject: _subject_hours(self.course_config, student.first_subject),
        }
        for sub in student.second_subjects:
            req[sub] = _subject_hours(self.course_config, sub)
        return req

    def required_component_hours(self, student: Student) -> dict[tuple[str, str], int]:
        subjects = ["语文", "数学", student.language, student.first_subject, *student.second_subjects]
        out: dict[tuple[str, str], int] = {}
        for subject in subjects:
            for comp in self.course_config.get(subject, []):
                out[(subject, comp["name"])] = int(comp["hours"])
        return out


def _subject_hours(course_config: dict[str, list[dict[str, Any]]], subject: str) -> int:
    return sum(int(c["hours"]) for c in course_config.get(subject, []))


def validate_scenario_shape(scenario: Scenario) -> list[str]:
    """Cheap data sanity checks.  Returns human-readable error strings."""
    errors: list[str] = []
    if not scenario.students:
        errors.append("学生数据为空")
    if not scenario.teachers:
        errors.append("教师数据为空")
    if not scenario.rooms:
        errors.append("教室数据为空")
    admin_classes = scenario.admin_classes()
    if len(admin_classes) > 20:
        errors.append("V0.1 单场景行政班数量上限为20")
    seen_students: set[str] = set()
    for s in scenario.students:
        if s.id in seen_students:
            errors.append(f"学生编号重复: {s.id}")
        seen_students.add(s.id)
        if s.language not in LANGUAGES:
            errors.append(f"{s.id} 外语无效: {s.language}")
        if s.first_subject not in FIRST_SUBJECTS:
            errors.append(f"{s.id} 首选科目无效: {s.first_subject}")
        if len(set(s.second_subjects)) != 2 or any(x not in SECOND_SUBJECTS for x in s.second_subjects):
            errors.append(f"{s.id} 再选科目必须从四科中选两科且不重复")
    seen_teachers: set[str] = set()
    for t in scenario.teachers:
        if t.id in seen_teachers:
            errors.append(f"教师编号重复: {t.id}")
        seen_teachers.add(t.id)
        if t.subject not in SUBJECTS:
            errors.append(f"{t.id} 教师科目无效: {t.subject}")
    for r in scenario.rooms:
        if r.capacity <= 0:
            errors.append(f"教室 {r.id} 容量必须大于0")
    active = scenario.active_slots()
    if len(active) == 0:
        errors.append("没有可排课的教学时段")
    for phase in ("elective", "foreign", "base"):
        if not any(s.phase == phase for s in active):
            errors.append(f"时间模型缺少 {phase} 时段")
    return errors
