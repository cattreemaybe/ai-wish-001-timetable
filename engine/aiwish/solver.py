"""CP-SAT time placement for a built plan.

Only OR-Tools CP-SAT decides the final time slot of every lesson.  The builder
has already fixed class membership, teachers and rooms; this module adds every
hard constraint again and optimises the configured soft weights.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model

from .builder import BuiltPlan, LessonTask, PlanningError
from .domain import STATUS_ZH, Scenario


@dataclass
class SolveOptions:
    time_limit_seconds: int = 30
    num_workers: int = 8
    random_seed: int = 20261125
    weights: dict[str, float] | None = None
    verbose: bool = False


class SolverInputError(Exception):
    pass


def _ordered_pool(plan: BuiltPlan, pool: str) -> list[str]:
    return list(plan.pools[pool])


def _build_hints(plan: BuiltPlan) -> dict[str, str]:
    """A deterministic starting point.  Hints are not constraints."""
    slots = plan.scenario.active_slots()
    by_label = {s.label: s for s in slots}
    base_labels = sorted(plan.pools["base"], key=lambda x: by_label[x].index)
    hints: dict[str, str] = {}

    # Per-admin-class base pattern: five Chinese positions and the remaining
    # eight positions for math.  Class 0 and class 7 share a Chinese teacher,
    # and their patterns are disjoint, so the hint itself is conflict-free for
    # the supplied 7 Chinese teachers.
    admin_names = sorted({t.admin_classes[0] for t in plan.tasks
                          if t.phase == "base" and t.admin_classes})
    for i, admin in enumerate(admin_names):
        chinese_positions = sorted({(2 * i + 5 * k) % 13 for k in range(5)})
        if len(chinese_positions) < 5:
            chinese_positions = sorted(set(chinese_positions) | set(range(13)))[:5]
        chinese_positions = sorted(chinese_positions)[:5]
        math_positions = [j for j in range(13) if j not in chinese_positions]
        chinese_tasks = sorted(
            [t for t in plan.tasks if t.phase == "base" and t.subject == "语文"
             and t.admin_classes == [admin]],
            key=lambda t: t.sequence,
        )
        math_tasks = sorted(
            [t for t in plan.tasks if t.phase == "base" and t.subject == "数学"
             and t.admin_classes == [admin]],
            key=lambda t: t.sequence,
        )
        for task, pos in zip(chinese_tasks, chinese_positions):
            hints[task.id] = base_labels[pos]
        for task, pos in zip(math_tasks, math_positions):
            hints[task.id] = base_labels[pos]

    # For fixed-pool classes (foreign and electives), all tasks of a class group
    # use the complete pool.  Sequentially placing them produces a clean
    # lecture/practice spread and helps the solver start from a complete roster.
    for cls in plan.classes:
        if cls.phase == "base":
            continue
        pool_key = ("foreign" if cls.phase == "foreign"
                    else "first" if cls.band == "first"
                    else cls.band)
        pool = sorted(plan.pools[pool_key], key=lambda x: by_label[x].index)
        tasks = sorted([t for t in plan.tasks if t.class_id == cls.id],
                       key=lambda t: t.sequence)
        if len(tasks) == len(pool):
            for task, label in zip(tasks, pool):
                hints[task.id] = label
        else:
            for task, label in zip(tasks, pool):
                hints[task.id] = label
    return hints


def solve_plan(plan: BuiltPlan, options: SolveOptions | None = None) -> dict[str, Any]:
    options = options or SolveOptions()
    scenario = plan.scenario
    slots = scenario.active_slots()
    by_label = {s.label: s for s in slots}
    slot_by_index = {s.index: s for s in slots}
    all_labels = [s.label for s in slots]
    tasks = plan.tasks
    class_by_id = {c.id: c for c in plan.classes}
    teacher_by_id = {t.id: t for t in scenario.teachers}

    model = cp_model.CpModel()
    x: dict[tuple[str, int], cp_model.IntVar] = {}
    assigned: dict[str, cp_model.IntVar] = {}
    task_slot_labels: dict[str, list[str]] = {}
    for task in tasks:
        teacher = teacher_by_id.get(task.teacher_id)
        unavailable = set(teacher.unavailable_slots if teacher else [])
        labels = [label for label in task.allowed_slots if label not in unavailable]
        if not labels:
            raise SolverInputError(
                f"教学任务 {task.id}（{task.class_name}/{task.component}）"
                f"的教师 {task.teacher_id} 在所有可排时段都不可用"
            )
        task_slot_labels[task.id] = labels
        vars_for_task = []
        for label in labels:
            slot = by_label[label]
            v = model.NewBoolVar(f"x_{task.id}_{slot.index}")
            x[(task.id, slot.index)] = v
            vars_for_task.append(v)
        model.Add(sum(vars_for_task) == 1)
        assigned[task.id] = model.NewIntVar(0, 35, f"slot_{task.id}")
        model.Add(assigned[task.id] == sum(by_label[label].index * x[(task.id, by_label[label].index)]
                                           for label in labels))

    # One task per class group per slot (implied by shared students, but kept
    # explicit for clarity and stronger propagation).
    by_class: dict[str, list[LessonTask]] = {}
    for task in tasks:
        by_class.setdefault(task.class_id, []).append(task)
    for cid, group_tasks in by_class.items():
        for slot in slots:
            terms = [x[(t.id, slot.index)] for t in group_tasks
                     if (t.id, slot.index) in x]
            if len(terms) > 1:
                model.Add(sum(terms) <= 1)

    # Student conflicts: every student attends exactly one lesson in every
    # active slot.  The count equality follows from 31 weekly tasks / 31 active
    # slots.  Writing it as equality is a strong and truthful propagation.
    tasks_by_student: dict[str, list[LessonTask]] = {}
    for task in tasks:
        for sid in task.student_ids:
            tasks_by_student.setdefault(sid, []).append(task)
    for sid, student_tasks in tasks_by_student.items():
        for slot in slots:
            terms = [x[(t.id, slot.index)] for t in student_tasks
                     if (t.id, slot.index) in x]
            model.Add(sum(terms) == 1)

    # Teacher conflicts.
    tasks_by_teacher: dict[str, list[LessonTask]] = {}
    for task in tasks:
        tasks_by_teacher.setdefault(task.teacher_id, []).append(task)
    for tid, teacher_tasks in tasks_by_teacher.items():
        for slot in slots:
            terms = [x[(t.id, slot.index)] for t in teacher_tasks
                     if (t.id, slot.index) in x]
            if len(terms) > 1:
                model.Add(sum(terms) <= 1)

    # Optional teacher weekly maximum.
    for tid, teacher in teacher_by_id.items():
        if teacher.max_weekly_periods is None:
            continue
        teacher_tasks = tasks_by_teacher.get(tid, [])
        terms = [x[(t.id, by_label[label].index)] for t in teacher_tasks
                 for label in task_slot_labels[t.id] if (t.id, by_label[label].index) in x]
        model.Add(sum(terms) <= int(teacher.max_weekly_periods))

    # Room conflicts.
    tasks_by_room: dict[str, list[LessonTask]] = {}
    for task in tasks:
        tasks_by_room.setdefault(task.room_id, []).append(task)
    for rid, room_tasks in tasks_by_room.items():
        for slot in slots:
            terms = [x[(t.id, slot.index)] for t in room_tasks
                     if (t.id, slot.index) in x]
            if len(terms) > 1:
                model.Add(sum(terms) <= 1)

    # Same subject, same class, same day: <= 2.
    by_class_day: dict[tuple[str, int], list[LessonTask]] = {}
    for cid, group_tasks in by_class.items():
        dates = sorted({by_label[label].day_index
                        for t in group_tasks for label in task_slot_labels[t.id]})
        for d in dates:
            by_class_day[(cid, d)] = group_tasks
    for (cid, d), group_tasks in by_class_day.items():
        terms = [x[(t.id, slot.index)] for t in group_tasks for slot in slots
                 if slot.day_index == d and (t.id, slot.index) in x]
        if terms:
            model.Add(sum(terms) <= 2)

    # Math: chronological sequence must be L,P,L,P,...  The builder generated
    # alternating task kinds and sequence numbers; the order constraints below
    # make that sequence the actual weekly sequence.
    for cls in plan.classes:
        if cls.subject != "数学":
            continue
        group = sorted(by_class[cls.id], key=lambda t: t.sequence)
        if [t.kind for t in group] != ["lecture", "practice"] * (len(group) // 2):
            raise SolverInputError(f"{cls.name} 的数学任务未按正课/落实课交替生成")
        for a, b in zip(group, group[1:]):
            model.Add(assigned[a.id] + 1 <= assigned[b.id])

    # Optional tentative 2-admin-class cap is enforced at build time.  If a
    # caller has enabled it, add a defensive validator-side check only.

    # Soft constraints actually represented in the objective.
    weights = dict(options.weights or scenario.rules.get("weights", {}))
    penalty_terms: list[Any] = []
    order_weight = int(weights.get("lecture_before_practice", 0) or 0)
    if order_weight:
        for cls in plan.classes:
            group = by_class[cls.id]
            lectures = [t for t in group if t.kind == "lecture"]
            practices = [t for t in group if t.kind == "practice"]
            if not lectures or not practices:
                continue
            for lec in lectures:
                for pra in practices:
                    if pra.sequence < lec.sequence:
                        continue
                    bad = model.NewBoolVar(f"late_{cls.id}_{lec.id}_{pra.id}")
                    model.Add(assigned[pra.id] < assigned[lec.id]).OnlyEnforceIf(bad)
                    model.Add(assigned[pra.id] >= assigned[lec.id]).OnlyEnforceIf(bad.Not())
                    penalty_terms.append(bad * order_weight)

    # Teacher idle is reported as a metric.  A compactness objective is added
    # only for teachers with at least three tasks, so it does not distort the
    # tiny scenarios.
    idle_weight = int(weights.get("teacher_idle", 0) or 0)
    idle_terms: list[Any] = []
    if idle_weight:
        for tid, teacher_tasks in tasks_by_teacher.items():
            if len(teacher_tasks) < 3:
                continue
            for day in sorted({by_label[label].day_index for t in teacher_tasks for label in task_slot_labels[t.id]}):
                day_slots = [s for s in slots if s.day_index == day]
                used = []
                for slot in day_slots:
                    terms = [x[(t.id, slot.index)] for t in teacher_tasks
                             if (t.id, slot.index) in x]
                    if not terms:
                        continue
                    u = model.NewBoolVar(f"u_{tid}_{day}_{slot.index}")
                    model.Add(sum(terms) == 1).OnlyEnforceIf(u)
                    model.Add(sum(terms) == 0).OnlyEnforceIf(u.Not())
                    used.append((slot.index, u))
                if len(used) < 2:
                    continue
                positions = [pos for pos, _ in used]
                first = model.NewIntVar(min(positions), max(positions), f"first_{tid}_{day}")
                last = model.NewIntVar(min(positions), max(positions), f"last_{tid}_{day}")
                total = model.NewIntVar(0, len(used), f"used_{tid}_{day}")
                model.Add(total == sum(u for _, u in used))
                for pos, u in used:
                    model.Add(first <= pos).OnlyEnforceIf(u)
                    model.Add(last >= pos).OnlyEnforceIf(u)
                idle = model.NewIntVar(0, len(used), f"idle_{tid}_{day}")
                model.Add(idle >= last - first + 1 - total)
                idle_terms.append(idle * idle_weight)
                # If no task at all, force idle to 0 by preferring the lower bound.
                no_task = model.NewBoolVar(f"no_{tid}_{day}")
                model.Add(total == 0).OnlyEnforceIf(no_task)
                model.Add(total >= 1).OnlyEnforceIf(no_task.Not())
                model.Add(idle == 0).OnlyEnforceIf(no_task)
    penalty_terms.extend(idle_terms)
    if penalty_terms:
        model.Minimize(sum(penalty_terms))

    # Hints: every variable is hinted exactly once.
    hints = _build_hints(plan)
    for task in tasks:
        for label in task_slot_labels[task.id]:
            key = (task.id, by_label[label].index)
            if key in x:
                model.AddHint(x[key], 1 if hints.get(task.id) == label else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(options.time_limit_seconds)
    solver.parameters.num_search_workers = max(1, int(options.num_workers or 1))
    solver.parameters.random_seed = int(options.random_seed)
    solver.parameters.log_search_progress = bool(options.verbose)
    solver.parameters.cp_model_presolve = True
    started = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - started
    status_name = solver.StatusName(status)

    result: dict[str, Any] = {
        "solver_status": status_name,
        "status_zh": STATUS_ZH.get(status_name, status_name),
        "status": _api_status(status_name),
        "solve_seconds": round(elapsed, 3),
        "objective_value": None,
        "variables": len(model.Proto().variables),
        "constraints": len(model.Proto().constraints),
        "hint_count": len(hints),
        "message": "",
        "tasks": [],
        "metrics": {},
    }
    if status_name in ("OPTIMAL", "FEASIBLE"):
        result["objective_value"] = solver.ObjectiveValue() if penalty_terms else 0.0
        scheduled = _materialize(plan, solver, x, assigned, by_label)
        result["tasks"] = scheduled
        result["metrics"] = compute_metrics(plan, scheduled)
        result["message"] = ("CP-SAT 已找到可行解并完成时间安排。" if status_name == "FEASIBLE"
                             else "CP-SAT 已证明该目标下的最优解。")
    elif status_name == "INFEASIBLE":
        result["message"] = "CP-SAT 证明在已启用硬约束下无可行解；未放宽任何硬约束。"
    elif status_name == "UNKNOWN":
        result["message"] = ("在时间限制内未找到可行解，也未证明无解。"
                             "这不等于无解，可增加时间或检查教师资源后重试。")
    else:
        result["message"] = f"求解器返回 {status_name}，请检查模型或数据。"
    return result


def _api_status(status_name: str) -> str:
    if status_name in ("OPTIMAL", "FEASIBLE"):
        return "solved"
    if status_name == "INFEASIBLE":
        return "infeasible"
    if status_name == "UNKNOWN":
        return "timeout"
    return "error"


def _materialize(
    plan: BuiltPlan, solver: cp_model.CpSolver,
    x: dict[tuple[str, int], cp_model.IntVar],
    assigned: dict[str, cp_model.IntVar], by_label: dict[str, Any],
) -> list[dict[str, Any]]:
    scheduled: list[dict[str, Any]] = []
    for task in plan.tasks:
        label = None
        for allowed in task.allowed_slots:
            slot = by_label[allowed]
            key = (task.id, slot.index)
            if key in x and solver.Value(x[key]):
                label = allowed
                break
        if label is None:
            raise RuntimeError(f"无法从解中读取任务 {task.id} 的时段")
        slot = by_label[label]
        d = task.to_dict()
        d.update({
            "slot_label": label, "slot_index": slot.index,
            "day": slot.day, "day_index": slot.day_index, "period": slot.period,
            "activity": slot.activity,
            "slot_phase": slot.phase, "slot_band": slot.band,
            "phase": task.phase, "band": task.band,
            "is_elective": task.phase == "elective",
        })
        scheduled.append(d)
    scheduled.sort(key=lambda t: (t["slot_index"], t["class_id"], t["id"]))
    return scheduled


def compute_metrics(plan: BuiltPlan, scheduled: list[dict[str, Any]]) -> dict[str, Any]:
    scenario = plan.scenario
    class_by_id = {c.id: c for c in plan.classes}
    roster_by_admin: dict[str, set[str]] = {}
    for s in scenario.students:
        roster_by_admin.setdefault(s.admin_class, set()).add(s.id)
    student_count = len(scenario.students)
    tasks_by_student: dict[str, list[dict[str, Any]]] = {}
    for t in scheduled:
        for sid in t["student_ids"]:
            tasks_by_student.setdefault(sid, []).append(t)
    walking_students = 0
    walk_transitions = 0
    for sid, st_tasks in tasks_by_student.items():
        st_tasks = sorted(st_tasks, key=lambda t: t["slot_index"])
        admin = next(s.admin_class for s in scenario.students if s.id == sid)
        roster = roster_by_admin[admin]
        has_walk = False
        for t in st_tasks:
            if not t["is_elective"]:
                continue
            if set(t["student_ids"]) != roster:
                has_walk = True
        electives = [t for t in st_tasks if t["is_elective"]]
        for a, b in zip(electives, electives[1:]):
            if set(a["student_ids"]) != set(b["student_ids"]):
                walk_transitions += 1
                has_walk = True
        if has_walk:
            walking_students += 1
    merged = [c for c in plan.classes if c.is_merged]
    merged_elective = [c for c in merged if c.kind.startswith("elective")]
    # Teacher idle periods, counted over active slots only.
    teacher_idle = 0
    teacher_day_counts = 0
    by_teacher: dict[str, list[dict[str, Any]]] = {}
    for t in scheduled:
        by_teacher.setdefault(t["teacher_id"], []).append(t)
    for tid, ts in by_teacher.items():
        days = sorted({t["day_index"] for t in ts})
        for day in days:
            day_tasks = [t for t in ts if t["day_index"] == day]
            positions = sorted({t["slot_index"] for t in day_tasks})
            if len(positions) < 2:
                continue
            day_slots = [s for s in scenario.active_slots() if s.day_index == day]
            active_positions = [s.index for s in day_slots]
            span = [p for p in active_positions if positions[0] <= p <= positions[-1]]
            idle = len(span) - len(positions)
            if idle > 0:
                teacher_idle += idle
                teacher_day_counts += 1
    # Section sizes / merge statistics.
    elective_classes = [c for c in plan.classes if c.kind.startswith("elective")]
    class_sizes = [c.size for c in plan.classes]
    metrics = {
        "student_count": student_count,
        "teacher_count": len(scenario.teachers),
        "room_count": len(scenario.rooms),
        "admin_class_count": len(scenario.admin_classes()),
        "teaching_class_count": len(plan.classes),
        "base_class_count": len([c for c in plan.classes if c.kind == "admin_base"]),
        "foreign_class_count": len([c for c in plan.classes if c.kind == "foreign"]),
        "elective_class_count": len(elective_classes),
        "merged_class_count": len(merged),
        "merged_elective_class_count": len(merged_elective),
        "walking_student_count": walking_students,
        "walking_student_ratio": round(walking_students / student_count, 4) if student_count else 0,
        "student_walk_transitions": walk_transitions,
        "teacher_idle_periods": teacher_idle,
        "teacher_idle_teacher_days": teacher_day_counts,
        "avg_class_size": round(sum(class_sizes) / len(class_sizes), 1) if class_sizes else 0,
        "min_class_size": min(class_sizes) if class_sizes else 0,
        "max_class_size": max(class_sizes) if class_sizes else 0,
        "elective_band_subjects": {
            band: sorted({c.subject for c in elective_classes if c.band == band})
            for band in ("first", "second_a", "second_b")
        },
        "weekly_task_count": len(scheduled),
        "scheduled_slots": len({t["slot_label"] for t in scheduled}),
        "total_student_lessons": sum(len(t["student_ids"]) for t in scheduled),
        "room_utilization": round(
            len(scheduled) / (len(scenario.rooms) * len(scenario.active_slots())), 4
        ) if scenario.rooms and scenario.active_slots() else 0,
    }
    return metrics
