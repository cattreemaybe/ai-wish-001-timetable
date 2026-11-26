"""Deterministic simulated data for scenarios A-G.

All names and numbers are fictional.  Every scenario uses a fixed seed and the
same generator; there are no hand-written timetables hiding in the data.
"""
from __future__ import annotations

import copy
import random
from typing import Any

from .domain import (
    DEFAULT_COURSE_CONFIG, DEFAULT_RULES, Scenario, Student, Teacher, Room,
    default_time_model, build_default_time_slots,
)

ALL_COMBOS: list[tuple[str, str, str]] = []
for _first in ("物理", "历史"):
    for _i in range(4):
        for _j in range(_i + 1, 4):
            ALL_COMBOS.append((_first, ("生物", "化学", "地理", "政治")[_i],
                               ("生物", "化学", "地理", "政治")[_j]))

TEACHER_COUNTS = {
    "语文": 7, "数学": 15, "英语": 8, "日语": 2, "物理": 3,
    "化学": 3, "生物": 3, "政治": 9, "历史": 6, "地理": 6,
}

SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
GIVEN = ["子涵", "一诺", "浩宇", "雨桐", "明轩", "思远", "嘉怡", "俊杰",
         "欣妍", "天佑", "若曦", "哲宇", "诗涵", "博文", "语嫣", "承泽"]
TEACHER_GIVEN = ["老师"]


def _scenario_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "A", "seed": 1101, "classes": 1, "students_per_class": 40,
            "name": "A · 无走班普通行政班",
            "description": "单一行政班、单一选科组合，验证最基础的课时与资源约束。",
            "kind": "single_combo", "language_mix": 0.0,
            "notes": "无走班。整班同一组合，教学班与行政班成员完全一致。",
        },
        {
            "id": "B", "seed": 1102, "classes": 1, "students_per_class": 40,
            "name": "B · 班内两种选科组合",
            "description": "同一行政班内同时存在物理类和历史类组合，触发班内走班。",
            "kind": "two_combo", "language_mix": 0.0,
            "notes": "班内两种组合，学生按首选科目分流。",
        },
        {
            "id": "C", "seed": 1103, "classes": 2, "students_per_class": 40,
            "name": "C · 两班物理历史同步走班",
            "description": "两个行政班混合首选科目，验证物理/历史同步走班与跨班合班。",
            "kind": "physics_history", "language_mix": 0.0,
            "notes": "两班物理、历史学生重新编班；首选科目只与彼此同步。",
        },
        {
            "id": "D", "seed": 1104, "classes": 2, "students_per_class": 40,
            "name": "D · 四选二两科/三科走班",
            "description": "再选科目覆盖全部六个组合，采用有序配对形成每段最多三科同步。",
            "kind": "four_choice", "language_mix": 0.0,
            "notes": "每段最多三科同时走班，绝不出现四科同时走班。",
        },
        {
            "id": "E", "seed": 1105, "classes": 2, "students_per_class": 40,
            "name": "E · 英语日语混合走班",
            "description": "英语、日语学生混合，外语教学班跨行政班重组。",
            "kind": "language", "language_mix": 0.5,
            "notes": "外语只与外语同步；英语/日语各自成班并可跨班合班。",
        },
        {
            "id": "F", "seed": 20261125, "classes": 8, "students_per_class": 40,
            "name": "F · 综合场景（320人）",
            "description": "8个行政班、320名学生，覆盖24种外语×选科组合、教师不可排时间与教室容量。",
            "kind": "comprehensive", "language_mix": 0.09,
            "notes": "综合验收场景。所有数据由固定种子生成，不围绕预设课表反向构造。",
        },
        {
            "id": "G", "seed": 1107, "classes": 8, "students_per_class": 40,
            "name": "G · 故意资源不足",
            "description": "综合场景的变体：物理教师仅1人，用于验证无解识别，不得放宽硬约束。",
            "kind": "infeasible", "language_mix": 0.05,
            "notes": "物理3个教学班需要3名教师同时授课，但只有1名物理教师，证明无解。",
            "teacher_overrides": {"物理": 1},
        },
    ]


def _student_name(rng: random.Random, idx: int) -> str:
    return f"{SURNAMES[idx % len(SURNAMES)]}{GIVEN[idx % len(GIVEN)]}{idx // 100 or ''}"


def _combos_for_kind(kind: str) -> list[tuple[str, str, str]]:
    if kind == "single_combo":
        return [("物理", "生物", "化学")]
    if kind == "two_combo":
        return [("物理", "生物", "化学"), ("历史", "政治", "地理")]
    if kind == "physics_history":
        return [("物理", "生物", "化学"), ("历史", "生物", "化学")]
    if kind == "language":
        return [("物理", "生物", "化学"), ("历史", "政治", "地理")]
    return list(ALL_COMBOS)


def _make_assignments(spec: dict[str, Any], rng: random.Random) -> list[dict[str, Any]]:
    """Assign each of the N students a combination and a language."""
    n = spec["classes"] * spec["students_per_class"]
    kind = spec["kind"]
    if kind == "single_combo":
        combos = [("物理", "生物", "化学")] * n
    elif kind == "two_combo":
        combos = [("物理", "生物", "化学") if i % 2 == 0 else ("历史", "政治", "地理")
                  for i in range(n)]
        rng.shuffle(combos)
    elif kind == "physics_history":
        combos = []
        for _ in range(n):
            if rng.random() < 0.5:
                combos.append(("物理", "生物", "化学"))
            else:
                combos.append(("历史", "生物", "化学"))
    elif kind == "four_choice":
        pairs = [("生物", "化学"), ("生物", "地理"), ("生物", "政治"),
                 ("化学", "地理"), ("化学", "政治"), ("地理", "政治")]
        combos = []
        for i in range(n):
            first = "物理" if i % 2 == 0 else "历史"
            pair = pairs[i % 6]
            combos.append((first, pair[0], pair[1]))
        rng.shuffle(combos)
    elif kind == "language":
        combos = [("物理", "生物", "化学"), ("历史", "政治", "地理")] * (n // 2)
        combos += [("物理", "化学", "地理")] * (n - len(combos))
        rng.shuffle(combos)
    else:
        # Balanced quota across the 12 combinations, then shuffle globally.
        combos = []
        base = n // len(ALL_COMBOS)
        rem = n % len(ALL_COMBOS)
        for i, combo in enumerate(ALL_COMBOS):
            combos.extend([combo] * (base + (1 if i < rem else 0)))
        rng.shuffle(combos)
    language_mix = float(spec.get("language_mix", 0.0))
    languages = ["日语" if rng.random() < language_mix else "英语" for _ in range(n)]
    # Guarantee at least one Japanese student in E/F if the mix asks for it.
    if language_mix > 0 and "日语" not in languages:
        languages[0] = "日语"
    return [
        {"first": c[0], "seconds": [c[1], c[2]], "language": languages[i]}
        for i, c in enumerate(combos)
    ]


def _make_students(spec: dict[str, Any], rng: random.Random) -> list[Student]:
    assignments = _make_assignments(spec, rng)
    students: list[Student] = []
    idx = 0
    for c in range(spec["classes"]):
        class_name = f"高一({c + 1})班"
        # Mix assignments across classes but keep exactly students_per_class.
        for _ in range(spec["students_per_class"]):
            a = assignments[idx]
            sid = f"S{idx + 1:03d}"
            students.append(Student(
                id=sid, name=_student_name(rng, idx), admin_class=class_name,
                language=a["language"], first_subject=a["first"],
                second_subjects=list(a["seconds"]),
            ))
            idx += 1
    return students


def _phase_slots() -> dict[str, list[str]]:
    slots = build_default_time_slots()
    out: dict[str, list[str]] = {"base": [], "foreign": [], "first": [], "second_a": [], "second_b": []}
    for s in slots:
        if not s.active:
            continue
        if s.phase == "base":
            out["base"].append(s.label)
        elif s.phase == "foreign":
            out["foreign"].append(s.label)
        elif s.phase == "elective":
            out[s.band].append(s.label)
    return out


def _make_teachers(spec: dict[str, Any], rng: random.Random) -> list[Teacher]:
    counts = dict(TEACHER_COUNTS)
    counts.update(spec.get("teacher_overrides", {}))
    pools = _phase_slots()
    teachers: list[Teacher] = []
    subject_index: dict[str, int] = {}
    for subject in ["语文", "数学", "英语", "日语", "物理", "历史", "生物", "化学", "地理", "政治"]:
        for i in range(counts.get(subject, 0)):
            subject_index[subject] = subject_index.get(subject, 0) + 1
            idx = subject_index[subject]
            tid = f"T-{_subject_code(subject)}-{idx:02d}"
            unavailable: list[str] = []
            if subject == "数学":
                # Math teachers carry genuine unavailable slots.  Chinese
                # teachers remain fully available so that the fixed 13-slot
                # base block always has at least one legal lesson per student.
                for key in rng.sample(pools["base"], k=min(len(pools["base"]), rng.choice([1, 2, 3]))):
                    unavailable.append(key)
            elif subject == "英语":
                # Keep seven teachers fully available for all 6 foreign slots;
                # the eighth is a genuine (but non-fatal) availability limit.
                if idx == 8:
                    unavailable.extend(pools["foreign"][:2])
            elif subject == "日语":
                if idx == 2:
                    unavailable.extend(pools["foreign"][:2])
            elif subject in ("物理", "历史", "生物", "化学", "地理", "政治"):
                # Keep required teachers free in their band.  Unavailability is
                # still generated in base slots so the hard constraint is real.
                if idx > 1:
                    for key in rng.sample(pools["base"], k=1):
                        unavailable.append(key)
            teachers.append(Teacher(
                id=tid, name=f"{subject}{idx:02d}", subject=subject,
                unavailable_slots=sorted(set(unavailable)),
                candidate_subjects=[subject],
            ))
    return teachers


def _subject_code(subject: str) -> str:
    return {
        "语文": "CN", "数学": "MA", "英语": "EN", "日语": "JP", "物理": "PH",
        "历史": "HI", "生物": "BI", "化学": "CH", "地理": "GE", "政治": "PO",
    }[subject]


def _make_rooms() -> list[Room]:
    rooms: list[Room] = []
    for i in range(1, 11):
        rooms.append(Room(id=f"R45-{i:02d}", name=f"A{i:03d}", capacity=45, building="A座"))
    for i in range(1, 13):
        rooms.append(Room(id=f"R60-{i:02d}", name=f"B{i:03d}", capacity=60, building="B座"))
    for i in range(1, 5):
        rooms.append(Room(id=f"R30-{i:02d}", name=f"C{i:03d}", capacity=30, building="C座"))
    return rooms


def _coordinate_base_availability(students: list[Student], teachers: list[Teacher]) -> None:
    """Avoid a data-generated dead slot where both base teachers are absent.

    The time model has exactly 13 base slots for 13 Chinese/math lessons per
    student.  If both the Chinese and the math teacher of an admin class are
    unavailable in the same slot, that student has no legal lesson at all.  We
    keep genuine unavailability constraints but remove such impossible overlaps
    from the simulated data, because this is a data feasibility issue rather
    than a solver behaviour we want to hide.
    """
    base_slots = [s.label for s in build_default_time_slots()
                  if s.active and s.phase == "base"]
    cn = sorted([t for t in teachers if t.subject == "语文"], key=lambda t: t.id)
    ma = sorted([t for t in teachers if t.subject == "数学"], key=lambda t: t.id)
    admins = []
    for s in students:
        if s.admin_class not in admins:
            admins.append(s.admin_class)
    if not cn or not ma:
        return
    for i, _admin in enumerate(admins):
        c = cn[i % len(cn)]
        m = ma[i % len(ma)]
        bad = set(c.unavailable_slots) & set(m.unavailable_slots) & set(base_slots)
        if bad:
            c.unavailable_slots = [x for x in c.unavailable_slots if x not in bad]
        # Keep at least the five Chinese and eight math lessons schedulable.
        c_free = [x for x in base_slots if x not in set(c.unavailable_slots)]
        if len(c_free) < 5:
            extra = [x for x in c.unavailable_slots if x in base_slots][:5 - len(c_free)]
            c.unavailable_slots = [x for x in c.unavailable_slots if x not in extra]
        m_free = [x for x in base_slots if x not in set(m.unavailable_slots)]
        if len(m_free) < 8:
            extra = [x for x in m.unavailable_slots if x in base_slots][:8 - len(m_free)]
            m.unavailable_slots = [x for x in m.unavailable_slots if x not in extra]


def build_scenario(spec: dict[str, Any]) -> Scenario:
    rng = random.Random(spec["seed"])
    students = _make_students(spec, rng)
    teachers = _make_teachers(spec, rng)
    _coordinate_base_availability(students, teachers)
    rules = copy.deepcopy(DEFAULT_RULES)
    if spec["id"] == "G":
        rules["enabled_hard_constraints"] = list(rules["enabled_hard_constraints"])
    scenario = Scenario(
        id=spec["id"], name=spec["name"], description=spec["description"],
        seed=spec["seed"], time_model=default_time_model(),
        course_config=copy.deepcopy(DEFAULT_COURSE_CONFIG),
        students=students, teachers=teachers, rooms=_make_rooms(), rules=rules,
        notes=spec.get("notes", ""),
        assumption_tags=[
            "行政班已分好", "每班40人", "教师自动预分配", "首选科目与历史同步",
            "再选科目按有序配对分两段", "周六周日为非标准时间模型",
        ],
    )
    return scenario


def build_all_scenarios() -> dict[str, Scenario]:
    return {spec["id"]: build_scenario(spec) for spec in _scenario_specs()}


def scenario_summaries() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in _scenario_specs():
        scenario = build_scenario(spec)
        out.append({
            "id": scenario.id, "name": scenario.name,
            "description": scenario.description,
            "seed": scenario.seed,
            "students": len(scenario.students),
            "teachers": len(scenario.teachers),
            "rooms": len(scenario.rooms),
            "admin_classes": len(scenario.admin_classes()),
            "kind": spec["kind"],
            "notes": scenario.notes,
        })
    return out
