"""API serialization helpers: scenario analysis and timetable views."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from aiwish.domain import (
    SECOND_SUBJECTS, LANGUAGES, SUBJECTS, build_default_time_slots,
)


def scenario_analysis(doc: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible wrapper around the engine analysis module."""
    from aiwish.analysis import analyze_doc
    return analyze_doc(doc)


def scenario_view(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["analysis"] = scenario_analysis(doc)
    return out


def enrich_result(result: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
    """Attach display names without changing ids or solver output."""
    teachers = {t["id"]: t for t in doc.get("teachers", [])}
    rooms = {r["id"]: r for r in doc.get("rooms", [])}
    students = {s["id"]: s for s in doc.get("students", [])}
    classes = []
    for c in result.get("classes", []):
        d = dict(c)
        d["teacher_name"] = teachers.get(c.get("teacher_id"), {}).get("name", c.get("teacher_id"))
        d["room_name"] = rooms.get(c.get("room_id"), {}).get("name", c.get("room_id"))
        classes.append(d)
    tasks = []
    for t in result.get("tasks", []):
        d = dict(t)
        d["teacher_name"] = teachers.get(t.get("teacher_id"), {}).get("name", t.get("teacher_id"))
        d["room_name"] = rooms.get(t.get("room_id"), {}).get("name", t.get("room_id"))
        d["student_names"] = [students[s]["name"] for s in t.get("student_ids", []) if s in students][:8]
        tasks.append(d)
    out = dict(result)
    out["classes"] = classes
    out["tasks"] = tasks
    out["scenario_summary"] = {
        "id": doc.get("id"), "name": doc.get("name"),
        "description": doc.get("description"), "seed": doc.get("seed"),
        "students": len(doc.get("students", [])),
        "teachers": len(doc.get("teachers", [])),
        "rooms": len(doc.get("rooms", [])),
    }
    return out


def view_entities(doc: dict[str, Any], view: str) -> list[dict[str, Any]]:
    if view == "admin":
        sizes = Counter(s["admin_class"] for s in doc.get("students", []))
        return [{"id": k, "name": k, "size": v} for k, v in sorted(sizes.items())]
    if view == "student":
        return [
            {"id": s["id"], "name": s["name"], "admin_class": s["admin_class"],
             "language": s["language"], "first_subject": s["first_subject"],
             "second_subjects": s["second_subjects"]}
            for s in doc.get("students", [])
        ]
    if view == "teacher":
        return [
            {"id": t["id"], "name": t["name"], "subject": t["subject"],
             "unavailable_slots": t.get("unavailable_slots", [])}
            for t in doc.get("teachers", [])
        ]
    if view == "room":
        return [
            {"id": r["id"], "name": r["name"], "capacity": r["capacity"],
             "building": r.get("building", "")}
            for r in doc.get("rooms", [])
        ]
    if view == "class":
        return [
            {"id": c["id"], "name": c["name"], "subject": c["subject"],
             "size": c.get("size", len(c.get("student_ids", [])))}
            for c in result_classes_placeholder(doc)
        ]
    return []


def result_classes_placeholder(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return []


def build_timetable(
    doc: dict[str, Any], result: dict[str, Any], view: str, entity_id: str
) -> dict[str, Any]:
    if view not in ("admin", "student", "teacher", "room", "class"):
        raise ValueError("view 必须是 admin/student/teacher/room/class")
    tasks = _filter_tasks(result.get("tasks", []), view, entity_id)
    by_cell: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for t in tasks:
        by_cell[(t["day_index"], t["period"])].append(t)
    teachers = {t["id"]: t for t in doc.get("teachers", [])}
    rooms = {r["id"]: r for r in doc.get("rooms", [])}
    students = {s["id"]: s for s in doc.get("students", [])}
    cells = []
    slots = doc.get("time_model", {}).get("slots", [])
    for slot in slots:
        key = (slot["day_index"], slot["period"])
        cell_tasks = sorted(by_cell.get(key, []), key=lambda t: t["subject"])
        cells.append({
            "day_index": slot["day_index"], "day": slot["day"],
            "period": slot["period"], "label": slot["label"],
            "active": slot["active"], "activity": slot["activity"],
            "phase": slot.get("phase"), "band": slot.get("band"),
            "tasks": [_task_card(t, teachers, rooms, students) for t in cell_tasks],
        })
    return {
        "view": view, "entity_id": entity_id,
        "entity": _entity_label(doc, view, entity_id),
        "days": doc.get("time_model", {}).get("days", []),
        "periods": list(range(1, int(doc.get("time_model", {}).get("periods_per_day", 6)) + 1)),
        "cells": cells,
        "task_count": len(tasks),
    }


def _filter_tasks(tasks: list[dict[str, Any]], view: str, entity_id: str) -> list[dict[str, Any]]:
    if view == "admin":
        return [t for t in tasks if entity_id in t.get("admin_classes", [])]
    if view == "student":
        return [t for t in tasks if entity_id in t.get("student_ids", [])]
    if view == "teacher":
        return [t for t in tasks if t.get("teacher_id") == entity_id]
    if view == "room":
        return [t for t in tasks if t.get("room_id") == entity_id]
    return [t for t in tasks if t.get("class_id") == entity_id]


def _entity_label(doc: dict[str, Any], view: str, entity_id: str) -> dict[str, Any]:
    if view == "admin":
        return {"name": entity_id}
    if view == "student":
        s = next((x for x in doc.get("students", []) if x["id"] == entity_id), None)
        return s or {"name": entity_id}
    if view == "teacher":
        t = next((x for x in doc.get("teachers", []) if x["id"] == entity_id), None)
        return t or {"name": entity_id}
    if view == "room":
        r = next((x for x in doc.get("rooms", []) if x["id"] == entity_id), None)
        return r or {"name": entity_id}
    return {"name": entity_id}


def _task_card(
    task: dict[str, Any], teachers: dict[str, Any],
    rooms: dict[str, Any], students: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": task["id"], "class_id": task["class_id"],
        "class_name": task["class_name"], "subject": task["subject"],
        "component": task["component"], "kind": task["kind"],
        "teacher_id": task["teacher_id"],
        "teacher_name": teachers.get(task["teacher_id"], {}).get("name", task["teacher_id"]),
        "room_id": task["room_id"],
        "room_name": rooms.get(task["room_id"], {}).get("name", task["room_id"]),
        "student_count": len(task.get("student_ids", [])),
        "student_names": [students[s]["name"] for s in task.get("student_ids", [])[:6] if s in students],
        "admin_classes": task.get("admin_classes", []),
        "is_elective": task.get("is_elective", False),
        "band": task.get("band"),
    }
