"""Teaching-class construction and resource pre-assignment.

This is the staged decomposition described in the requirements:

1. partition students into teaching classes (base classes, language classes,
   first-choice sections, second-choice sections);
2. assign teachers and home rooms under capacity constraints;
3. hand the resulting lesson tasks to CP-SAT for time placement.

The stage-1/2 decisions are explicit and inspectable.  CP-SAT never invents a
timetable from a finished result; it only receives constraints and finds slot
assignments.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from .domain import (
    Scenario, Student, Teacher, Room, TimeSlot, SECOND_SUBJECT_ORDER, SUBJECT_SHORT,
)


class PlanningError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class LessonTask:
    id: str
    class_id: str
    class_name: str
    subject: str
    component: str
    kind: str
    sequence: int
    phase: str
    band: str
    student_ids: list[str]
    admin_classes: list[str]
    teacher_id: str
    room_id: str
    allowed_slots: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "class_id": self.class_id, "class_name": self.class_name,
            "subject": self.subject, "component": self.component,
            "kind": self.kind, "sequence": self.sequence,
            "phase": self.phase, "band": self.band,
            "student_ids": self.student_ids,
            "admin_classes": self.admin_classes,
            "teacher_id": self.teacher_id, "room_id": self.room_id,
            "allowed_slots": self.allowed_slots,
        }


@dataclass
class TeachingClass:
    id: str
    name: str
    subject: str
    kind: str          # admin_base / foreign / elective_first / elective_second
    phase: str
    band: str
    student_ids: list[str]
    admin_classes: list[str]
    teacher_id: str
    room_id: str
    components: list[dict[str, Any]]
    task_ids: list[str] = field(default_factory=list)
    required_hours: int = 0
    note: str = ""

    @property
    def size(self) -> int:
        return len(self.student_ids)

    @property
    def is_merged(self) -> bool:
        return len(self.admin_classes) > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "subject": self.subject,
            "kind": self.kind, "phase": self.phase, "band": self.band,
            "student_ids": self.student_ids, "admin_classes": self.admin_classes,
            "teacher_id": self.teacher_id, "room_id": self.room_id,
            "components": self.components, "task_ids": self.task_ids,
            "required_hours": self.required_hours,
            "size": self.size, "is_merged": self.is_merged, "note": self.note,
        }


@dataclass
class BuiltPlan:
    scenario: Scenario
    classes: list[TeachingClass]
    tasks: list[LessonTask]
    pools: dict[str, list[str]]
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "classes": [c.to_dict() for c in self.classes],
            "tasks": [t.to_dict() for t in self.tasks],
            "pools": self.pools,
            "diagnostics": self.diagnostics,
        }


def _admin_classes(students: Iterable[Student]) -> list[str]:
    out: list[str] = []
    for s in students:
        if s.admin_class not in out:
            out.append(s.admin_class)
    return out


def _split_balanced(students: list[Student], n_sections: int) -> list[list[Student]]:
    """Contiguous chunks over admin-class-sorted students, balanced by size.

    Contiguous chunks are deliberate: they create real cross-admin-class merged
    teaching classes instead of scattering every class across the whole grade.
    """
    ordered = sorted(students, key=lambda s: (s.admin_class, s.id))
    base = len(ordered) // n_sections
    rem = len(ordered) % n_sections
    out: list[list[Student]] = []
    start = 0
    for i in range(n_sections):
        size = base + (1 if i < rem else 0)
        out.append(ordered[start:start + size])
        start += size
    return [x for x in out if x]


def _split_capped_by_admin(
    students: list[Student], max_size: int, admin_cap: int
) -> list[list[Student]]:
    """Split while keeping each walk group to at most N admin classes."""
    ordered = sorted(students, key=lambda s: (s.admin_class, s.id))
    grouped: list[list[Student]] = []
    # Build windows of admin classes and chunk each window.
    by_admin: dict[str, list[Student]] = {}
    for s in ordered:
        by_admin.setdefault(s.admin_class, []).append(s)
    names = list(by_admin)
    current: list[Student] = []
    for i in range(0, len(names), admin_cap):
        window = [s for name in names[i:i + admin_cap] for s in by_admin[name]]
        grouped.extend(_split_balanced(window, max(1, math.ceil(len(window) / max_size))))
    return grouped


def _section_count(n: int, teacher_count: int, preferred: int = 54, hard_max: int = 60) -> int:
    if n <= 0:
        return 0
    count = max(1, math.ceil(n / preferred))
    if count > teacher_count:
        count = teacher_count
    if count <= 0:
        raise PlanningError("teacher_capacity", "该科目没有可用教师")
    if math.ceil(n / count) > hard_max:
        raise PlanningError(
            "capacity_conflict",
            f"{n} 名学生最多只能拆成 {count} 个教学班，按最大教室 {hard_max} 人仍超出容量",
            {"students": n, "sections": count, "hard_max": hard_max},
        )
    return count


class PlanBuilder:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.slots = scenario.active_slots()
        self.by_label = {s.label: s for s in self.slots}
        self.slots_by_phase: dict[str, list[TimeSlot]] = {}
        self.slots_by_band: dict[str, list[TimeSlot]] = {}
        for slot in self.slots:
            if slot.phase:
                self.slots_by_phase.setdefault(slot.phase, []).append(slot)
            if slot.band:
                self.slots_by_band.setdefault(slot.band, []).append(slot)
        self.teachers_by_subject: dict[str, list[Teacher]] = {}
        for t in scenario.teachers:
            for sub in (t.candidate_subjects or [t.subject]):
                self.teachers_by_subject.setdefault(sub, []).append(t)
        self.rooms_by_capacity = sorted(scenario.rooms, key=lambda r: (r.capacity, r.id))
        self.classes: list[TeachingClass] = []
        self.tasks: list[LessonTask] = []
        self._class_seq = 0
        self._task_seq = 0
        self._assignments: dict[str, int] = {}
        self._room_use: dict[str, set[str]] = {}
        self._used_full: dict[tuple[str, str], set[str]] = {}
        self.diagnostics: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ public
    def build(self) -> BuiltPlan:
        # Ensure the three phase pools have at least the required capacity.
        if len(self.slots_by_phase.get("base", [])) < 13:
            raise PlanningError("time_pool", "base 时段少于13节，无法容纳语文/数学共13节")
        if len(self.slots_by_phase.get("foreign", [])) < 6:
            raise PlanningError("time_pool", "foreign 时段少于6节，无法容纳外语共6节")
        for band in ("first", "second_a", "second_b"):
            if len(self.slots_by_band.get(band, [])) < 4:
                raise PlanningError("time_pool", f"{band} 走班时段少于4节")

        # 1. Base Chinese / math classes per admin class.
        for ac in self.scenario.admin_classes():
            self._build_cn_math(ac)
        # 2. Foreign language classes by language across admin classes.
        self._build_foreign()
        # 3. Elective first-choice sections.
        self._build_first_choice()
        # 4. Second-choice sections, split by ordered pair into bands A/B.
        self._build_second_choice()
        # 5. Deterministic room assignment.
        self._assign_rooms()

        if not self.tasks:
            raise PlanningError("empty_plan", "构建后没有教学任务")
        # Sanity: every student has exactly 31 tasks (the scenario's weekly load).
        counts: dict[str, int] = {}
        for task in self.tasks:
            for sid in task.student_ids:
                counts[sid] = counts.get(sid, 0) + 1
        bad = {sid: c for sid, c in counts.items() if c != 31}
        if bad:
            raise PlanningError("student_load", "学生课时任务数不等于31", {"bad": bad})
        return BuiltPlan(
            scenario=self.scenario, classes=self.classes, tasks=self.tasks,
            pools={
                "base": [s.label for s in self.slots_by_phase.get("base", [])],
                "foreign": [s.label for s in self.slots_by_phase.get("foreign", [])],
                "first": [s.label for s in self.slots_by_band.get("first", [])],
                "second_a": [s.label for s in self.slots_by_band.get("second_a", [])],
                "second_b": [s.label for s in self.slots_by_band.get("second_b", [])],
            },
            diagnostics=self.diagnostics,
        )

    # ------------------------------------------------------------- class groups
    def _new_class(
        self, name: str, subject: str, kind: str, phase: str, band: str,
        students: list[Student], components: list[dict[str, Any]],
        allowed_slots: list[TimeSlot], require_full: bool = False,
        band_key: str | None = None, binding_key: str | None = None,
    ) -> TeachingClass:
        self._class_seq += 1
        cid = f"C{self._class_seq:03d}"
        admins = _admin_classes(students)
        teacher = self._pick_teacher(subject, allowed_slots, require_full,
                                     band_key or band, binding_key=binding_key)
        comp_summary = [{"name": c["name"], "hours": int(c["hours"]), "kind": c["kind"]}
                        for c in components]
        cls = TeachingClass(
            id=cid, name=name, subject=subject, kind=kind, phase=phase,
            band=band, student_ids=[s.id for s in students],
            admin_classes=admins, teacher_id=teacher.id, room_id="",
            components=comp_summary, required_hours=sum(c["hours"] for c in components),
        )
        self.classes.append(cls)
        seq = 0
        for comp in components:
            for _ in range(int(comp["hours"])):
                self._task_seq += 1
                task = LessonTask(
                    id=f"K{self._task_seq:04d}", class_id=cls.id,
                    class_name=name, subject=subject,
                    component=comp["name"], kind=comp["kind"], sequence=seq,
                    phase=phase, band=band,
                    student_ids=list(cls.student_ids),
                    admin_classes=list(admins),
                    teacher_id=teacher.id, room_id="",
                    allowed_slots=[s.label for s in allowed_slots],
                )
                self.tasks.append(task)
                cls.task_ids.append(task.id)
                seq += 1
        return cls

    def _build_cn_math(self, admin_class: str) -> None:
        students = [s for s in self.scenario.students if s.admin_class == admin_class]
        base_slots = self.slots_by_phase["base"]
        cn_comps = self.scenario.course_config["语文"]
        ma_comps = self.scenario.course_config["数学"]
        self._new_class(
            f"语文·{admin_class}", "语文", "admin_base", "base", "base",
            students, cn_comps, base_slots, binding_key=f"语文|{admin_class}",
        )
        # Math sessions are separate one-hour tasks so the alternating order is
        # a genuine constraint, not a post-hoc claim.
        self._class_seq += 1
        cid = f"C{self._class_seq:03d}"
        teacher = self._pick_teacher("数学", base_slots, False, "base",
                                     binding_key=f"数学|{admin_class}")
        comps = [{"name": c["name"], "hours": int(c["hours"]), "kind": c["kind"]}
                 for c in ma_comps]
        cls = TeachingClass(
            id=cid, name=f"数学·{admin_class}", subject="数学", kind="admin_base",
            phase="base", band="base", student_ids=[s.id for s in students],
            admin_classes=[admin_class], teacher_id=teacher.id, room_id="",
            components=comps, required_hours=sum(c["hours"] for c in comps),
        )
        self.classes.append(cls)
        # Alternate lecture / practice: L, P, L, P, ... The solver is required
        # to keep chronological order, so the weekly sequence is exactly this.
        kinds = []
        lecture = next((c for c in ma_comps if c["kind"] == "lecture"), None)
        practice = next((c for c in ma_comps if c["kind"] == "practice"), None)
        if not lecture or not practice:
            raise PlanningError("config_error", "数学必须同时配置正课和落实课")
        n = int(lecture["hours"]) + int(practice["hours"])
        for i in range(n):
            comp = lecture if i % 2 == 0 else practice
            kinds.append((comp["name"], comp["kind"]))
        for seq, (comp_name, kind) in enumerate(kinds):
            self._task_seq += 1
            task = LessonTask(
                id=f"K{self._task_seq:04d}", class_id=cls.id,
                class_name=cls.name, subject="数学", component=comp_name,
                kind=kind, sequence=seq, phase="base", band="base",
                student_ids=list(cls.student_ids),
                admin_classes=[admin_class], teacher_id=teacher.id, room_id="",
                allowed_slots=[s.label for s in base_slots],
            )
            self.tasks.append(task)
            cls.task_ids.append(task.id)

    def _build_foreign(self) -> None:
        foreign_slots = self.slots_by_phase["foreign"]
        for language in ("英语", "日语"):
            students = [s for s in self.scenario.students if s.language == language]
            if not students:
                continue
            teachers = self._teachers_for(language)
            n = _section_count(len(students), len(teachers), preferred=54, hard_max=60)
            sections = _split_balanced(students, n)
            comps = self.scenario.course_config[language]
            for i, section in enumerate(sections, start=1):
                self._new_class(
                    f"{language}·{i:02d}班", language, "foreign", "foreign", "foreign",
                    section, comps, foreign_slots, require_full=True,
                    band_key=f"foreign:{language}", binding_key=f"{language}|{i:02d}",
                )

    def _build_first_choice(self) -> None:
        slots = self.slots_by_band["first"]
        for subject in ("物理", "历史"):
            students = [s for s in self.scenario.students if s.first_subject == subject]
            if not students:
                continue
            teachers = self._teachers_for(subject)
            n = _section_count(len(students), len(teachers), preferred=54, hard_max=60)
            cap = int(self.scenario.rules.get("walk_group_admin_class_cap") or 0)
            sections = (_split_capped_by_admin(students, 60, cap) if cap
                        else _split_balanced(students, n))
            if len(sections) > len(teachers):
                raise PlanningError(
                    "walk_cap_teacher_conflict",
                    f"{subject}按走班组不超过{cap}个行政班拆分后需要{len(sections)}个教学班，"
                    f"但只有{len(teachers)}名教师且同一时段必须同时授课",
                    {"subject": subject, "sections": len(sections), "teachers": len(teachers)},
                )
            comps = self.scenario.course_config[subject]
            for i, section in enumerate(sections, start=1):
                self._new_class(
                    f"{subject}·首选{i:02d}班", subject, "elective_first",
                    "elective", "first", section, comps, slots,
                    require_full=True, band_key=f"first:{subject}",
                    binding_key=f"{subject}|首选|{i:02d}",
                )

    def _build_second_choice(self) -> None:
        # Ordered pairing: for each student, the earlier subject in
        # SECOND_SUBJECT_ORDER goes to band A and the later one to band B.
        # Band A can only contain the first three subjects; band B only the last
        # three.  Therefore no band ever has four second-choice subjects.
        band_students: dict[str, dict[str, list[Student]]] = {
            "second_a": {s: [] for s in SECOND_SUBJECT_ORDER},
            "second_b": {s: [] for s in SECOND_SUBJECT_ORDER},
        }
        for student in self.scenario.students:
            ordered = sorted(student.second_subjects, key=SECOND_SUBJECT_ORDER.index)
            band_students["second_a"][ordered[0]].append(student)
            band_students["second_b"][ordered[1]].append(student)
        for band, by_subject in band_students.items():
            slots = self.slots_by_band[band]
            for subject, students in by_subject.items():
                if not students:
                    continue
                teachers = self._teachers_for(subject)
                n = _section_count(len(students), len(teachers), preferred=54, hard_max=60)
                cap = int(self.scenario.rules.get("walk_group_admin_class_cap") or 0)
                sections = (_split_capped_by_admin(students, 60, cap) if cap
                            else _split_balanced(students, n))
                if len(sections) > len(teachers):
                    raise PlanningError(
                        "walk_cap_teacher_conflict",
                        f"{subject}在{band}按走班组拆分后需要{len(sections)}名教师同时授课，"
                        f"但只有{len(teachers)}名",
                        {"subject": subject, "band": band,
                         "sections": len(sections), "teachers": len(teachers)},
                    )
                comps = self.scenario.course_config[subject]
                for i, section in enumerate(sections, start=1):
                    self._new_class(
                        f"{subject}·{'A' if band == 'second_a' else 'B'}段{i:02d}班",
                        subject, "elective_second", "elective", band,
                        section, comps, slots, require_full=True,
                        band_key=f"{band}:{subject}",
                        binding_key=f"{subject}|{band}|{i:02d}",
                    )

    # ------------------------------------------------------------------ teachers
    def _teachers_for(self, subject: str) -> list[Teacher]:
        return self.teachers_by_subject.get(subject, [])

    def _teacher_free(self, teacher: Teacher, slots: list[TimeSlot]) -> bool:
        unavailable = set(teacher.unavailable_slots)
        return all(s.label not in unavailable for s in slots)

    def _pick_teacher(
        self, subject: str, slots: list[TimeSlot], require_full: bool,
        band_key: str, binding_key: str | None = None,
    ) -> Teacher:
        candidates = self._teachers_for(subject)
        if not candidates:
            raise PlanningError("teacher_missing", f"科目 {subject} 没有候选教师")
        if binding_key:
            bound_id = self.scenario.teacher_bindings.get(binding_key)
            if bound_id:
                bound = next((t for t in candidates if t.id == bound_id), None)
                if bound is None:
                    raise PlanningError(
                        "teacher_binding",
                        f"{binding_key} 绑定的教师 {bound_id} 不存在或不是{subject}候选教师",
                        {"binding_key": binding_key, "teacher_id": bound_id},
                    )
                if require_full and not self._teacher_free(bound, slots):
                    raise PlanningError(
                        "teacher_binding_unavailable",
                        f"{binding_key} 绑定的教师 {bound.name} 在所需时段存在不可排时间",
                        {"binding_key": binding_key, "teacher_id": bound_id},
                    )
                if require_full:
                    used = self._used_full.setdefault((subject, band_key), set())
                    if bound.id in used:
                        raise PlanningError(
                            "teacher_binding_conflict",
                            f"{binding_key} 与同段其他教学班绑定了同一名教师 {bound.name}",
                            {"binding_key": binding_key, "teacher_id": bound_id},
                        )
                    used.add(bound.id)
                self._assignments[bound.id] = self._assignments.get(bound.id, 0) + 1
                return bound
        if require_full:
            candidates = [t for t in candidates if self._teacher_free(t, slots)]
            if not candidates:
                raise PlanningError(
                    "teacher_availability",
                    f"{subject} 在 {band_key} 没有完整可用的教师",
                    {"subject": subject, "band": band_key,
                     "slots": [s.label for s in slots]},
                )
            used = self._used_full.setdefault((subject, band_key), set())
            unused = [t for t in candidates if t.id not in used]
            if not unused:
                raise PlanningError(
                    "teacher_capacity",
                    f"{subject} 在 {band_key} 需要更多同时授课教师，"
                    f"但可完整排课的候选教师不足",
                    {"subject": subject, "band": band_key,
                     "required_sections": len(used) + 1,
                     "available_teachers": len(candidates)},
                )
            teacher = min(unused, key=lambda t: (self._assignments.get(t.id, 0), t.id))
            used.add(teacher.id)
        else:
            teacher = min(
                candidates,
                key=lambda t: (self._assignments.get(t.id, 0), len(t.unavailable_slots), t.id),
            )
        self._assignments[teacher.id] = self._assignments.get(teacher.id, 0) + 1
        # Weekly hard limits are checked by the validator on actual task counts.
        return teacher

    # --------------------------------------------------------------------- rooms
    def _pick_room(self, size: int) -> Room:
        for room in self.rooms_by_capacity:
            if room.capacity >= size:
                return room
        raise PlanningError(
            "room_capacity", f"教学班人数 {size} 超过所有教室容量",
            {"size": size, "max_capacity": max(r.capacity for r in self.scenario.rooms)},
        )

    def _assign_rooms(self) -> None:
        # Base: one home room per admin class (Chinese and math share it at
        # different times).  Distinct across admin classes.
        base_classes = [c for c in self.classes if c.kind == "admin_base"]
        base_rooms: dict[str, Room] = {}
        admin_names = sorted({a for c in base_classes for a in c.admin_classes})
        for i, admin in enumerate(admin_names):
            eligible = [r for r in self.scenario.rooms if r.capacity >= 40]
            if i >= len(eligible):
                raise PlanningError("room_capacity", "行政班数量超过可用教室数量")
            base_rooms[admin] = eligible[i]
        for c in base_classes:
            c.room_id = base_rooms[c.admin_classes[0]].id

        # Foreign: distinct room per concurrent language class.
        foreign_classes = [c for c in self.classes if c.kind == "foreign"]
        self._assign_distinct_rooms(foreign_classes, phase="foreign")
        # Electives: distinct room inside each band.
        for band in ("first", "second_a", "second_b"):
            section = [c for c in self.classes if c.kind.startswith("elective") and c.band == band]
            self._assign_distinct_rooms(section, phase=band)
        # Propagate room to tasks and check capacity.
        room_by_id = {r.id: r for r in self.scenario.rooms}
        for task in self.tasks:
            cls = next(c for c in self.classes if c.id == task.class_id)
            task.room_id = cls.room_id
            room = room_by_id[task.room_id]
            if room.capacity < len(task.student_ids):
                raise PlanningError(
                    "room_capacity",
                    f"{task.class_name} 有{len(task.student_ids)}人，"
                    f"但教室{room.name}仅{room.capacity}座",
                )

    def _assign_distinct_rooms(self, classes: list[TeachingClass], phase: str) -> None:
        used: set[str] = set()
        # Larger classes first; choose the smallest adequate room not yet used
        # in this concurrent band.
        for cls in sorted(classes, key=lambda c: (-c.size, c.id)):
            candidates = [r for r in self.rooms_by_capacity
                          if r.capacity >= cls.size and r.id not in used]
            if not candidates:
                raise PlanningError(
                    "room_conflict",
                    f"{phase} 时段同时需要 {len(classes)} 间容量足够的教室，但资源不足",
                    {"phase": phase, "classes": len(classes)},
                )
            room = candidates[0]
            used.add(room.id)
            cls.room_id = room.id
