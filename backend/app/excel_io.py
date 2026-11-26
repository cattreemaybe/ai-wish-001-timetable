"""Excel import/export for the workbench.

Exports contain the full scenario, all four timetable views and the validation
report.  Imports are deliberately strict: every row is validated and the
scenario is rejected if a student's subject combination is invalid.
"""
from __future__ import annotations

import io
from collections import defaultdict
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from aiwish.domain import (
    LANGUAGES, FIRST_SUBJECTS, SECOND_SUBJECTS, SUBJECTS, Scenario, validate_scenario_shape,
)

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
SUBHEADER_FILL = PatternFill("solid", fgColor="DCE6F1")
ACCENT_FILL = PatternFill("solid", fgColor="E8F1F2")
WARN_FILL = PatternFill("solid", fgColor="FCE8E6")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(size=16, bold=True, color="1F3A5F")
BORDER = Border(*[Side(style="thin", color="D0D7DE")] * 4)


def _sheet(wb: Workbook, title: str):
    ws = wb.create_sheet(title)
    ws.sheet_view.showGridLines = False
    return ws


def _header(ws, row: int, values: list[str]) -> None:
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
    ws.row_dimensions[row].height = 24


def _title(ws, text: str, cols: int = 8) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=cols)
    c = ws.cell(row=1, column=1, value=text)
    c.font = TITLE_FONT
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30


def _autosize(ws, max_width: int = 44) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = 10
        for cell in col:
            if cell.value is not None:
                width = max(width, min(max_width, len(str(cell.value)) * 1.3 + 2))
        ws.column_dimensions[letter].width = width


def _cell(ws, row: int, col: int, value: Any, fill=None, bold=False) -> None:
    c = ws.cell(row=row, column=col, value=value)
    c.border = BORDER
    c.alignment = Alignment(vertical="center", wrap_text=True)
    if fill:
        c.fill = fill
    if bold:
        c.font = Font(bold=True)


def export_workbook(doc: dict[str, Any], result: dict[str, Any]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    _overview(wb, doc, result)
    _students_sheet(wb, doc)
    _teachers_sheet(wb, doc)
    _courses_sheet(wb, doc)
    _rooms_sheet(wb, doc)
    _classes_sheet(wb, doc, result)
    _admin_sheets(wb, doc, result)
    _long_sheet(wb, doc, result, "student")
    _long_sheet(wb, doc, result, "teacher")
    _long_sheet(wb, doc, result, "room")
    _validation_sheet(wb, result)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _overview(wb: Workbook, doc: dict[str, Any], result: dict[str, Any]) -> None:
    ws = _sheet(wb, "总览")
    _title(ws, f"AI-WISH-001 走班排课工作台 · {doc.get('name', '')}", 6)
    rows = [
        ("场景编号", doc.get("id")), ("场景描述", doc.get("description")),
        ("随机种子", doc.get("seed")), ("学生数", len(doc.get("students", []))),
        ("教师数", len(doc.get("teachers", []))), ("教室数", len(doc.get("rooms", []))),
        ("行政班数", len({s["admin_class"] for s in doc.get("students", [])})),
        ("求解状态", result.get("solver_status")), ("状态说明", result.get("status_zh")),
        ("求解耗时(秒)", result.get("solve_seconds")),
        ("构建耗时(秒)", result.get("build_seconds")),
        ("校验结果", "通过" if (result.get("validation") or {}).get("passed") else "未通过/无课表"),
        ("课表是否过期", "是（基础数据已修改，需重算）" if result.get("is_stale") else "否"),
        ("说明", result.get("message")),
    ]
    r = 3
    for k, v in rows:
        _cell(ws, r, 1, k, SUBHEADER_FILL, True)
        _cell(ws, r, 2, v)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        r += 1
    r += 1
    _cell(ws, r, 1, "核心指标", HEADER_FILL, True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    r += 1
    for k, v in (result.get("metrics") or {}).items():
        if isinstance(v, (dict, list)):
            v = str(v)
        _cell(ws, r, 1, k, ACCENT_FILL, True)
        _cell(ws, r, 2, v)
        r += 1
    _autosize(ws)


def _students_sheet(wb: Workbook, doc: dict[str, Any]) -> None:
    ws = _sheet(wb, "学生选科")
    _title(ws, "学生选科数据（导入模板同名工作表可回写）", 8)
    _header(ws, 3, ["学号", "姓名", "行政班", "外语", "首选科目", "再选1", "再选2", "备注"])
    for i, s in enumerate(doc.get("students", []), start=4):
        for j, v in enumerate([
            s["id"], s["name"], s["admin_class"], s["language"],
            s["first_subject"], s["second_subjects"][0], s["second_subjects"][1], "",
        ], start=1):
            _cell(ws, i, j, v)
    ws.freeze_panes = "A4"
    _autosize(ws)


def _teachers_sheet(wb: Workbook, doc: dict[str, Any]) -> None:
    ws = _sheet(wb, "教师资源")
    _title(ws, "教师资源（不可排时间用分号或逗号分隔）", 6)
    _header(ws, 3, ["工号", "姓名", "科目", "不可排时间", "候选科目", "周课时上限"])
    for i, t in enumerate(doc.get("teachers", []), start=4):
        for j, v in enumerate([
            t["id"], t["name"], t["subject"], "；".join(t.get("unavailable_slots", [])),
            "、".join(t.get("candidate_subjects", [t["subject"]])),
            t.get("max_weekly_periods") or "",
        ], start=1):
            _cell(ws, i, j, v)
    ws.freeze_panes = "A4"
    _autosize(ws)


def _courses_sheet(wb: Workbook, doc: dict[str, Any]) -> None:
    ws = _sheet(wb, "课程配置")
    _title(ws, "课程课时配置（周课时）", 4)
    _header(ws, 3, ["科目", "细分课程", "周课时", "类型"])
    r = 4
    for subject, comps in doc.get("course_config", {}).items():
        for c in comps:
            for j, v in enumerate([subject, c["name"], c["hours"], c.get("kind", "")], start=1):
                _cell(ws, r, j, v)
            r += 1
    ws.freeze_panes = "A4"
    _autosize(ws)


def _rooms_sheet(wb: Workbook, doc: dict[str, Any]) -> None:
    ws = _sheet(wb, "教室资源")
    _title(ws, "教室资源", 5)
    _header(ws, 3, ["教室编号", "教室名称", "容量", "楼栋", "备注"])
    for i, r in enumerate(doc.get("rooms", []), start=4):
        for j, v in enumerate([r["id"], r["name"], r["capacity"], r.get("building", ""), ""], start=1):
            _cell(ws, i, j, v)
    ws.freeze_panes = "A4"
    _autosize(ws)


def _classes_sheet(wb: Workbook, doc: dict[str, Any], result: dict[str, Any]) -> None:
    ws = _sheet(wb, "教学班")
    _title(ws, "教学班与走班关系", 10)
    _header(ws, 3, ["教学班编号", "名称", "科目", "类型", "走班段", "人数",
                    "行政班", "任课教师", "教室", "周课时"])
    teachers = {t["id"]: t["name"] for t in doc.get("teachers", [])}
    rooms = {r["id"]: r["name"] for r in doc.get("rooms", [])}
    for i, c in enumerate(result.get("classes", []), start=4):
        for j, v in enumerate([
            c["id"], c["name"], c["subject"], c["kind"], c.get("band", ""),
            c.get("size", len(c.get("student_ids", []))),
            "、".join(c.get("admin_classes", [])),
            teachers.get(c.get("teacher_id"), c.get("teacher_id")),
            rooms.get(c.get("room_id"), c.get("room_id")),
            c.get("required_hours", ""),
        ], start=1):
            _cell(ws, i, j, v)
    ws.freeze_panes = "A4"
    _autosize(ws)


def _admin_sheets(wb: Workbook, doc: dict[str, Any], result: dict[str, Any]) -> None:
    ws = _sheet(wb, "行政班课表")
    _title(ws, "行政班课表（走班时段可能同一格出现多个教学班）", 9)
    slots = doc.get("time_model", {}).get("slots", [])
    by_cell: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for t in result.get("tasks", []):
        by_cell[(t["day_index"], t["period"])].append(t)
    r = 3
    for admin in sorted({s["admin_class"] for s in doc.get("students", [])}):
        _cell(ws, r, 1, f"行政班：{admin}", HEADER_FILL, True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        r += 1
        _header(ws, r, ["节次"] + doc.get("time_model", {}).get("days", []))
        r += 1
        for period in range(1, int(doc.get("time_model", {}).get("periods_per_day", 6)) + 1):
            _cell(ws, r, 1, f"第{period}节", SUBHEADER_FILL, True)
            for d, day in enumerate(doc.get("time_model", {}).get("days", [])):
                slot = next((s for s in slots if s["day_index"] == d and s["period"] == period), None)
                tasks = [t for t in by_cell.get((d, period), []) if admin in t.get("admin_classes", [])]
                if not slot or not slot.get("active"):
                    text = slot.get("activity", "") if slot else ""
                elif tasks:
                    text = " / ".join(
                        f"{t['subject']}·{t['component']}({t['class_name']})" for t in tasks
                    )
                else:
                    text = ""
                _cell(ws, r, d + 2, text, ACCENT_FILL if tasks else None)
            r += 1
        r += 2
    _autosize(ws, 36)


def _long_sheet(wb: Workbook, doc: dict[str, Any], result: dict[str, Any], kind: str) -> None:
    titles = {"student": "学生课表", "teacher": "教师课表", "room": "教室课表"}
    ws = _sheet(wb, titles[kind])
    _title(ws, titles[kind] + "（长表，便于筛选与核对）", 8)
    _header(ws, 3, ["对象", "日期", "节次", "科目", "细分课程", "教学班", "教师", "教室"])
    teachers = {t["id"]: t["name"] for t in doc.get("teachers", [])}
    rooms = {r["id"]: r["name"] for r in doc.get("rooms", [])}
    students = {s["id"]: s for s in doc.get("students", [])}
    rows: list[tuple[str, dict[str, Any]]] = []
    for t in result.get("tasks", []):
        if kind == "student":
            for sid in t.get("student_ids", []):
                rows.append((f"{sid} {students.get(sid, {}).get('name', '')}", t))
        elif kind == "teacher":
            rows.append((f"{t['teacher_id']} {teachers.get(t['teacher_id'], '')}", t))
        else:
            rows.append((f"{t['room_id']} {rooms.get(t['room_id'], '')}", t))
    rows.sort(key=lambda x: (x[0], x[1]["slot_index"]))
    for i, (obj, t) in enumerate(rows, start=4):
        for j, v in enumerate([
            obj, t["day"], f"第{t['period']}节", t["subject"], t["component"],
            t["class_name"], teachers.get(t["teacher_id"], t["teacher_id"]),
            rooms.get(t["room_id"], t["room_id"]),
        ], start=1):
            _cell(ws, i, j, v)
    ws.freeze_panes = "A4"
    _autosize(ws)


def _validation_sheet(wb: Workbook, result: dict[str, Any]) -> None:
    ws = _sheet(wb, "校验结果")
    _title(ws, "独立校验器结果", 4)
    val = result.get("validation") or {}
    summary = val.get("summary") or {}
    _header(ws, 3, ["检查项", "数值", "状态", "说明"])
    r = 4
    for k, v in summary.items():
        _cell(ws, r, 1, k, ACCENT_FILL, True)
        _cell(ws, r, 2, v)
        _cell(ws, r, 3, "通过" if v in (0, True, None) else "未通过")
        _cell(ws, r, 4, "")
        r += 1
    r += 1
    _header(ws, r, ["违规代码", "类别", "范围", "说明"])
    r += 1
    for v in val.get("violations", []):
        for j, value in enumerate([v.get("code"), v.get("category"), v.get("scope"), v.get("message")], start=1):
            _cell(ws, r, j, value, WARN_FILL if j == 1 else None)
        r += 1
    _autosize(ws)


def template_workbook(doc: dict[str, Any], only_sheet: str | None = None) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    intro = _sheet(wb, "填写说明")
    _title(intro, "AI-WISH-001 基础数据导入模板", 2)
    notes = [
        "1. 学生表：每行一名学生；学号唯一；外语=英语/日语；首选=物理/历史；再选1、再选2从生物/化学/地理/政治中选两科且不重复。",
        "2. 教师表：不可排时间用分号分隔，例如：周一第1节；周三第4节；候选科目用、分隔。",
        "3. 教室表：容量必须为正整数。",
        "4. 课程配置表：同一科目的多行细分课程会自动合并，周课时为整数。",
        "5. 导入为“替换”时会替换对应工作表的数据；“合并”时按编号更新/追加。",
        "6. 导入只处理基础数据，不导入课表；导入后需重新自动排课。",
    ]
    for i, note in enumerate(notes, start=3):
        intro.merge_cells(start_row=i, start_column=1, end_row=i, end_column=2)
        c = intro.cell(row=i, column=1, value=note)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        intro.row_dimensions[i].height = 34

    if only_sheet in (None, "students"):
        ws = _sheet(wb, "学生")
        _header(ws, 1, ["学号", "姓名", "行政班", "外语", "首选科目", "再选1", "再选2"])
        samples = doc.get("students", [])[:2]
        for i, s in enumerate(samples, start=2):
            for j, v in enumerate([s["id"], s["name"], s["admin_class"], s["language"],
                                   s["first_subject"], s["second_subjects"][0],
                                   s["second_subjects"][1]], start=1):
                _cell(ws, i, j, v)
        ws.freeze_panes = "A2"
        _autosize(ws)
    if only_sheet in (None, "teachers"):
        ws = _sheet(wb, "教师")
        _header(ws, 1, ["工号", "姓名", "科目", "不可排时间", "候选科目", "周课时上限"])
        for i, t in enumerate(doc.get("teachers", [])[:2], start=2):
            for j, v in enumerate([t["id"], t["name"], t["subject"],
                                   "；".join(t.get("unavailable_slots", [])),
                                   "、".join(t.get("candidate_subjects", [t["subject"]])),
                                   t.get("max_weekly_periods") or ""], start=1):
                _cell(ws, i, j, v)
        ws.freeze_panes = "A2"
        _autosize(ws)
    if only_sheet in (None, "rooms"):
        ws = _sheet(wb, "教室")
        _header(ws, 1, ["教室编号", "教室名称", "容量", "楼栋"])
        for i, r in enumerate(doc.get("rooms", [])[:2], start=2):
            for j, v in enumerate([r["id"], r["name"], r["capacity"], r.get("building", "")], start=1):
                _cell(ws, i, j, v)
        ws.freeze_panes = "A2"
        _autosize(ws)
    if only_sheet in (None, "courses"):
        ws = _sheet(wb, "课程配置")
        _header(ws, 1, ["科目", "细分课程", "周课时", "类型"])
        r = 2
        for subject, comps in doc.get("course_config", {}).items():
            for c in comps:
                for j, v in enumerate([subject, c["name"], c["hours"], c.get("kind", "")], start=1):
                    _cell(ws, r, j, v)
                r += 1
        ws.freeze_panes = "A2"
        _autosize(ws)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _read_rows(ws, required: list[str]) -> list[dict[str, Any]]:
    """Read a sheet, locating its header row.

    Import templates put headers on row 1; exported workbooks have a title and
    metadata above the header.  Both are accepted, which makes export/import a
    true round trip.
    """
    raw = list(ws.iter_rows(values_only=True))
    if not raw:
        return []
    header_index = 0
    for i, row in enumerate(raw[:12]):
        values = [str(x).strip() if x is not None else "" for x in row]
        if all(token in values for token in required):
            header_index = i
            break
    headers = [str(x).strip() if x is not None else "" for x in raw[header_index]]
    out = []
    for row in raw[header_index + 1:]:
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        out.append({headers[i]: row[i] for i in range(min(len(headers), len(row)))})
    return out


def _split_list(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value)
    for sep in ("；", ";", "、", "，", ",", "|"):
        text = text.replace(sep, "|")
    return [x.strip() for x in text.split("|") if x.strip()]


def import_workbook(content: bytes, doc: dict[str, Any], mode: str = "replace", only_sheet: str | None = None) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    errors: list[str] = []
    duplicates: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {
        "students": 0, "teachers": 0, "rooms": 0, "course_rows": 0,
        "duplicates": duplicates, "warnings": warnings, "failed_rows": 0,
    }
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True)
    except Exception as exc:  # noqa: BLE001
        return doc, [f"无法读取 Excel：{exc}"], summary
    out = dict(doc)

    student_sheet = next((n for n in ("学生", "学生选科") if n in wb.sheetnames), None)
    if only_sheet in (None, "students") and student_sheet:
        ws = wb[student_sheet]
        rows = _read_rows(ws, ["学号", "姓名", "行政班", "外语"])
        students = []
        seen_students: set[str] = set()
        for idx, row in enumerate(rows, start=2):
            sid = str(row.get("学号") or "").strip()
            name = str(row.get("姓名") or "").strip()
            admin = str(row.get("行政班") or "").strip()
            lang = str(row.get("外语") or "").strip()
            first = str(row.get("首选科目") or "").strip()
            sec1 = str(row.get("再选1") or "").strip()
            sec2 = str(row.get("再选2") or "").strip()
            if not all([sid, name, admin, lang, first, sec1, sec2]):
                errors.append(f"学生表第{idx}行存在空单元格")
                summary["failed_rows"] += 1
                continue
            if sid in seen_students:
                duplicates.append(f"学生表学号重复：{sid}")
                continue
            seen_students.add(sid)
            if lang not in LANGUAGES:
                errors.append(f"学生表第{idx}行外语无效：{lang}")
            if first not in FIRST_SUBJECTS:
                errors.append(f"学生表第{idx}行首选科目无效：{first}")
            if sec1 not in SECOND_SUBJECTS or sec2 not in SECOND_SUBJECTS or sec1 == sec2:
                errors.append(f"学生表第{idx}行再选科目无效：{sec1}/{sec2}")
            if lang not in LANGUAGES or first not in FIRST_SUBJECTS or sec1 not in SECOND_SUBJECTS or sec2 not in SECOND_SUBJECTS or sec1 == sec2:
                summary["failed_rows"] += 1
            students.append({
                "id": sid, "name": name, "admin_class": admin,
                "language": lang, "first_subject": first,
                "second_subjects": [sec1, sec2],
            })
        if not students:
            errors.append("学生表没有可导入的数据")
        if not errors:
            existing = {s["id"]: s for s in out.get("students", [])} if mode == "merge" else {}
            for s in students:
                existing[s["id"]] = s
            out["students"] = list(existing.values())
            summary["students"] = len(students)

    teacher_sheet = next((n for n in ("教师", "教师资源") if n in wb.sheetnames), None)
    if only_sheet in (None, "teachers") and teacher_sheet:
        ws = wb[teacher_sheet]
        rows = _read_rows(ws, ["工号", "姓名", "科目"])
        teachers = []
        seen_teachers: set[str] = set()
        for idx, row in enumerate(rows, start=2):
            tid = str(row.get("工号") or "").strip()
            name = str(row.get("姓名") or "").strip()
            subject = str(row.get("科目") or "").strip()
            if not all([tid, name, subject]):
                errors.append(f"教师表第{idx}行缺少工号/姓名/科目")
                summary["failed_rows"] += 1
                continue
            if tid in seen_teachers:
                duplicates.append(f"教师表工号重复：{tid}")
                continue
            seen_teachers.add(tid)
            if subject not in SUBJECTS:
                errors.append(f"教师表第{idx}行科目无效：{subject}")
                continue
            teachers.append({
                "id": tid, "name": name, "subject": subject,
                "unavailable_slots": _split_list(row.get("不可排时间")),
                "candidate_subjects": _split_list(row.get("候选科目")) or [subject],
                "max_weekly_periods": int(row["周课时上限"]) if str(row.get("周课时上限") or "").strip().isdigit() else None,
            })
        if not teachers:
            errors.append("教师表没有可导入的数据")
        if not errors:
            existing = {t["id"]: t for t in out.get("teachers", [])} if mode == "merge" else {}
            for t in teachers:
                existing[t["id"]] = t
            out["teachers"] = list(existing.values())
            summary["teachers"] = len(teachers)

    room_sheet = next((n for n in ("教室", "教室资源") if n in wb.sheetnames), None)
    if only_sheet in (None, "rooms") and room_sheet:
        ws = wb[room_sheet]
        rows = _read_rows(ws, ["教室编号", "教室名称", "容量"])
        rooms = []
        seen_rooms: set[str] = set()
        for idx, row in enumerate(rows, start=2):
            rid = str(row.get("教室编号") or "").strip()
            name = str(row.get("教室名称") or "").strip()
            cap_raw = row.get("容量")
            if not rid or not name or cap_raw is None or str(cap_raw).strip() == "":
                errors.append(f"教室表第{idx}行缺少编号/名称/容量")
                summary["failed_rows"] += 1
                continue
            if rid in seen_rooms:
                duplicates.append(f"教室表编号重复：{rid}")
                continue
            seen_rooms.add(rid)
            try:
                cap = int(float(str(cap_raw)))
            except ValueError:
                errors.append(f"教室表第{idx}行容量不是整数：{cap_raw}")
                continue
            rooms.append({"id": rid, "name": name, "capacity": cap,
                          "building": str(row.get("楼栋") or "教学楼")})
        if not rooms:
            errors.append("教室表没有可导入的数据")
        if not errors:
            existing = {r["id"]: r for r in out.get("rooms", [])} if mode == "merge" else {}
            for r in rooms:
                existing[r["id"]] = r
            out["rooms"] = list(existing.values())
            summary["rooms"] = len(rooms)

    if only_sheet in (None, "courses") and "课程配置" in wb.sheetnames:
        ws = wb["课程配置"]
        rows = _read_rows(ws, ["科目", "细分课程", "周课时"])
        config: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for idx, row in enumerate(rows, start=2):
            subject = str(row.get("科目") or "").strip()
            comp = str(row.get("细分课程") or "").strip()
            hours_raw = row.get("周课时")
            if not subject or not comp or hours_raw is None:
                errors.append(f"课程配置第{idx}行缺少科目/细分课程/周课时")
                continue
            try:
                hours = int(float(str(hours_raw)))
            except ValueError:
                errors.append(f"课程配置第{idx}行周课时不是整数：{hours_raw}")
                continue
            config[subject].append({
                "name": comp, "hours": hours,
                "kind": str(row.get("类型") or "lecture"),
            })
            summary["course_rows"] += 1
        if not config:
            errors.append("课程配置表没有可导入的数据")
        if not errors and config:
            out["course_config"] = dict(config)

    if errors:
        return doc, errors, summary
    try:
        scenario = Scenario.from_dict(out)
    except Exception as exc:  # noqa: BLE001
        return doc, [f"导入数据无法构建场景：{exc}"], summary
    # A sheet-specific import must be allowed to fill a blank custom scenario
    # before the other categories exist.  Validate the global shape only for a
    # whole-workbook import.
    if only_sheet is None:
        shape = validate_scenario_shape(scenario)
        if shape:
            return doc, shape, summary
    out = scenario.to_dict()
    out["_updated_at"] = doc.get("_updated_at")
    return out, [], summary
