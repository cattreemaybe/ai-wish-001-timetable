"""FastAPI workbench API.

The API is a thin adapter around the independent `aiwish` engine.  It never
computes a timetable itself; every solve call goes through `run_scenario`.
"""
from __future__ import annotations

import copy
import os
from urllib.parse import quote
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aiwish.data_gen import build_all_scenarios, scenario_summaries
from aiwish.domain import (
    LANGUAGES, FIRST_SUBJECTS, SECOND_SUBJECTS, SUBJECTS, Scenario,
    DEFAULT_COURSE_CONFIG, DEFAULT_RULES,
    build_default_time_slots, default_time_model, validate_scenario_shape,
)
from aiwish.preflight import preflight_scenario
from aiwish.runner import run_scenario, validate_result

from .db import Database
from .excel_io import export_workbook, import_workbook, template_workbook
from .serializers import (
    build_timetable, enrich_result, scenario_analysis, scenario_view, view_entities,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = os.environ.get("AIWISH_DB", str(ROOT / "data" / "aiwish.db"))


class CustomScenarioRequest(BaseModel):
    name: str | None = None


class StudentCreate(BaseModel):
    name: str
    admin_class: str
    language: str
    first_subject: str
    second_subjects: list[str]


class TeacherCreate(BaseModel):
    name: str
    subject: str
    unavailable_slots: list[str] = Field(default_factory=list)
    max_weekly_periods: int | None = Field(default=None, ge=1, le=60)


class RoomCreate(BaseModel):
    name: str
    capacity: int = Field(ge=1, le=500)
    building: str = "教学楼"


class SolveRequest(BaseModel):
    time_limit_seconds: int | None = Field(default=None, ge=1, le=300)
    num_workers: int | None = Field(default=None, ge=1, le=32)
    weights: dict[str, float] | None = None


class StudentPatch(BaseModel):
    language: str | None = None
    first_subject: str | None = None
    second_subjects: list[str] | None = None
    admin_class: str | None = None


class TeacherPatch(BaseModel):
    unavailable_slots: list[str] | None = None
    max_weekly_periods: int | None = Field(default=None, ge=1, le=60)


class RoomPatch(BaseModel):
    capacity: int | None = Field(default=None, ge=1, le=500)
    name: str | None = None
    building: str | None = None


class RulesPatch(BaseModel):
    values: dict[str, Any]


class TeacherBindingsPatch(BaseModel):
    bindings: dict[str, str]


def create_app(db_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(
        title="AI-WISH-001 新高考智能走班排课工作台",
        version="0.1.0",
        description="真实 CP-SAT 排课、独立校验、四类课表与 Excel 交换。",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )
    db = Database(db_path or DEFAULT_DB)
    app.state.db = db

    # ------------------------------------------------------------------ helpers
    def get_doc_or_404(sid: str) -> dict[str, Any]:
        doc = db.get_scenario_doc(sid.upper())
        if not doc:
            raise HTTPException(404, f"场景 {sid} 不存在")
        return doc

    def save_doc(doc: dict[str, Any]) -> dict[str, Any]:
        sid = doc["id"]
        ts = db.save_scenario_doc(sid, doc)
        fresh = db.get_scenario_doc(sid)
        assert fresh is not None
        fresh["_updated_at"] = ts
        return fresh

    def scenario_payload(doc: dict[str, Any]) -> dict[str, Any]:
        view = scenario_view(doc)
        view["is_sample"] = doc["id"] in "ABCDEFG"
        latest = db.latest_run(doc["id"])
        view["latest_run"] = {
            "run_id": latest["run_id"], "status": latest["status"],
            "solver_status": latest["solver_status"],
            "validation_passed": (latest.get("validation") or {}).get("passed"),
            "is_stale": latest.get("scenario_updated_at") != doc.get("_updated_at"),
        } if latest else None
        return view

    # --------------------------------------------------------------------- meta
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "AI-WISH-001", "version": "0.1.0"}

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return {
            "version": "0.1.0",
            "engine": "OR-Tools CP-SAT",
            "statuses": {
                "OPTIMAL": "已找到最优解", "FEASIBLE": "已找到可行解",
                "INFEASIBLE": "已证明无解", "UNKNOWN": "超时且未找到可行解",
                "MODEL_INVALID": "模型或数据错误",
                "PRECHECK_INFEASIBLE": "数据预检证明无解",
            },
            "assumptions": [
                "31个教学时段与31周课时保持一致；学生每周无空堂。",
                "再选科目按固定顺序拆成A/B两段，每段最多3科同步，绝不4科同时走班。",
                "走班组最多两个行政班为待确认规则，默认未启用；启用后作为硬约束校验。",
                "教师为自动预分配，支持不可排时间；教师自动分配业务规则仍待确认。",
            ],
        }

    # ----------------------------------------------------------------- scenarios
    @app.get("/api/scenarios")
    def list_scenarios() -> list[dict[str, Any]]:
        summaries = {x["id"]: x for x in scenario_summaries()}
        out = []
        for row in db.list_scenarios():
            sid = row["id"]
            doc = db.get_scenario_doc(sid)
            if not doc:
                continue
            latest = db.latest_run(sid)
            item = dict(summaries.get(sid, {
                "id": sid, "name": doc.get("name", sid),
                "description": doc.get("description", ""),
                "kind": "custom",
            }))
            item.update({
                "name": doc.get("name", item.get("name", sid)),
                "description": doc.get("description", ""),
                "is_sample": sid in "ABCDEFG",
                "updated_at": row["updated_at"],
                "student_count": len(doc.get("students", [])),
                "teacher_count": len(doc.get("teachers", [])),
                "room_count": len(doc.get("rooms", [])),
                "admin_class_count": len({s["admin_class"] for s in doc.get("students", [])}),
                "latest_run": {
                    "run_id": latest["run_id"], "status": latest["status"],
                    "solver_status": latest["solver_status"],
                    "validation_passed": (latest.get("validation") or {}).get("passed"),
                    "solve_seconds": latest.get("solve_seconds"),
                } if latest else None,
            })
            out.append(item)
        return out

    @app.get("/api/scenarios/{sid}")
    def get_scenario(sid: str) -> dict[str, Any]:
        return scenario_payload(get_doc_or_404(sid))

    @app.post("/api/scenarios/custom")
    def create_custom_scenario(body: CustomScenarioRequest) -> dict[str, Any]:
        existing = {row["id"] for row in db.list_scenarios()}
        i = 1
        while f"MY{i:02d}" in existing:
            i += 1
        sid = f"MY{i:02d}"
        name = (body.name or "").strip() or ("我的排课方案" + ("" if i == 1 else f" {i}"))
        scenario = Scenario(
            id=sid, name=name,
            description="从空白数据开始创建：导入或手动录入学生、教师、教室，再配置课程、时间与规则。",
            seed=20261126 + i,
            time_model=default_time_model(),
            course_config=copy.deepcopy(DEFAULT_COURSE_CONFIG),
            students=[], teachers=[], rooms=[],
            rules=copy.deepcopy(DEFAULT_RULES),
            notes="自定义方案；未导入真实数据前不应排课。",
            assumption_tags=["自定义方案", "数据由用户导入或手动录入"],
        )
        db.save_scenario_doc(sid, scenario.to_dict())
        return scenario_payload(get_doc_or_404(sid))

    @app.get("/api/scenarios/{sid}/preflight")
    def preflight(sid: str) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        try:
            scenario = Scenario.from_dict(doc)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(422, f"场景数据无法加载：{exc}") from exc
        return preflight_scenario(scenario)

    @app.post("/api/scenarios/{sid}/reset")
    def reset_scenario(sid: str) -> dict[str, Any]:
        fresh = db.reset_scenario(sid.upper())
        if not fresh:
            raise HTTPException(404, f"场景 {sid} 不存在")
        return scenario_payload(fresh)

    @app.get("/api/scenarios/{sid}/analysis")
    def analysis(sid: str) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        return scenario_analysis(doc)

    # ------------------------------------------------------------------- editing
    @app.patch("/api/scenarios/{sid}/students/{student_id}")
    def patch_student(sid: str, student_id: str, body: StudentPatch) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        student = next((s for s in doc["students"] if s["id"] == student_id), None)
        if not student:
            raise HTTPException(404, f"学生 {student_id} 不存在")
        if body.language is not None:
            if body.language not in LANGUAGES:
                raise HTTPException(422, "外语必须是英语或日语")
            student["language"] = body.language
        if body.first_subject is not None:
            if body.first_subject not in FIRST_SUBJECTS:
                raise HTTPException(422, "首选科目必须是物理或历史")
            student["first_subject"] = body.first_subject
        if body.second_subjects is not None:
            subs = body.second_subjects
            if len(subs) != 2 or len(set(subs)) != 2 or any(s not in SECOND_SUBJECTS for s in subs):
                raise HTTPException(422, "再选科目必须从生物/化学/地理/政治中选两科且不重复")
            student["second_subjects"] = subs
        if body.admin_class is not None and body.admin_class.strip():
            student["admin_class"] = body.admin_class.strip()
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.post("/api/scenarios/{sid}/students")
    def add_student(sid: str, body: StudentCreate) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        if body.language not in LANGUAGES:
            raise HTTPException(422, "外语必须是英语或日语")
        if body.first_subject not in FIRST_SUBJECTS:
            raise HTTPException(422, "首选科目必须是物理或历史")
        if (len(body.second_subjects) != 2 or len(set(body.second_subjects)) != 2
                or any(s not in SECOND_SUBJECTS for s in body.second_subjects)):
            raise HTTPException(422, "再选科目必须从生物/化学/地理/政治中选两科且不重复")
        name = body.name.strip()
        admin = body.admin_class.strip()
        if not name or not admin:
            raise HTTPException(422, "姓名和行政班不能为空")
        nums = []
        for s in doc["students"]:
            if str(s.get("id", "")).startswith("S") and str(s.get("id", ""))[1:].isdigit():
                nums.append(int(str(s["id"])[1:]))
        new_id = f"S{(max(nums) + 1) if nums else 1:03d}"
        doc["students"].append({
            "id": new_id, "name": name, "admin_class": admin,
            "language": body.language, "first_subject": body.first_subject,
            "second_subjects": body.second_subjects,
        })
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.post("/api/scenarios/{sid}/teachers")
    def add_teacher(sid: str, body: TeacherCreate) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        if body.subject not in SUBJECTS:
            raise HTTPException(422, "教师科目无效")
        valid_labels = {s["label"] for s in doc["time_model"]["slots"]}
        unknown = [x for x in body.unavailable_slots if x not in valid_labels]
        if unknown:
            raise HTTPException(422, f"非法时段: {unknown[:3]}")
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "教师姓名不能为空")
        code = {
            "语文": "CN", "数学": "MA", "英语": "EN", "日语": "JP", "物理": "PH",
            "历史": "HI", "生物": "BI", "化学": "CH", "地理": "GE", "政治": "PO",
        }.get(body.subject, "XX")
        nums = []
        for t in doc["teachers"]:
            tid = str(t.get("id", ""))
            if tid.startswith(f"T-{code}-") and tid.split("-")[-1].isdigit():
                nums.append(int(tid.split("-")[-1]))
        new_id = f"T-{code}-{(max(nums) + 1) if nums else 1:02d}"
        doc["teachers"].append({
            "id": new_id, "name": name, "subject": body.subject,
            "unavailable_slots": sorted(set(body.unavailable_slots)),
            "candidate_subjects": [body.subject],
            "max_weekly_periods": body.max_weekly_periods,
        })
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.post("/api/scenarios/{sid}/rooms")
    def add_room(sid: str, body: RoomCreate) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "教室名称不能为空")
        nums = []
        for r in doc["rooms"]:
            rid = str(r.get("id", ""))
            if rid.startswith("ROOM-") and rid.split("-")[-1].isdigit():
                nums.append(int(rid.split("-")[-1]))
        new_id = f"ROOM-{(max(nums) + 1) if nums else 1:03d}"
        doc["rooms"].append({
            "id": new_id, "name": name, "capacity": body.capacity,
            "building": body.building.strip() or "教学楼",
        })
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.patch("/api/scenarios/{sid}/teachers/{teacher_id}")
    def patch_teacher(sid: str, teacher_id: str, body: TeacherPatch) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        teacher = next((t for t in doc["teachers"] if t["id"] == teacher_id), None)
        if not teacher:
            raise HTTPException(404, f"教师 {teacher_id} 不存在")
        valid_labels = {s["label"] for s in doc["time_model"]["slots"]}
        if body.unavailable_slots is not None:
            unknown = [x for x in body.unavailable_slots if x not in valid_labels]
            if unknown:
                raise HTTPException(422, f"非法时段: {unknown[:3]}")
            teacher["unavailable_slots"] = sorted(set(body.unavailable_slots))
        if body.max_weekly_periods is not None:
            teacher["max_weekly_periods"] = body.max_weekly_periods
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.patch("/api/scenarios/{sid}/rooms/{room_id}")
    def patch_room(sid: str, room_id: str, body: RoomPatch) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        room = next((r for r in doc["rooms"] if r["id"] == room_id), None)
        if not room:
            raise HTTPException(404, f"教室 {room_id} 不存在")
        if body.capacity is not None:
            room["capacity"] = body.capacity
        if body.name is not None:
            room["name"] = body.name
        if body.building is not None:
            room["building"] = body.building
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.put("/api/scenarios/{sid}/rules")
    def patch_rules(sid: str, body: RulesPatch) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        allowed = set(doc["rules"].keys())
        boolean_keys = {
            "teacher_no_overlap", "student_no_overlap", "room_no_overlap",
            "room_capacity", "prescribed_hours", "teacher_unavailable",
            "forbid_non_teaching_slots", "fixed_component_teacher",
            "max_two_same_subject_per_day", "math_lecture_practice_alternate",
            "physics_only_with_history", "foreign_only_with_foreign",
            "second_choice_max_three_subjects",
        }
        errors = []
        for key, value in body.values.items():
            if key not in allowed:
                errors.append(f"未知规则: {key}")
                continue
            if key in boolean_keys:
                if not isinstance(value, bool):
                    errors.append(f"{key} 必须是布尔值")
                elif value is not True:
                    errors.append(f"{key} 是 V0.1 固定硬约束，不允许关闭")
            if key == "enabled_hard_constraints":
                errors.append("enabled_hard_constraints 为只读字段；硬约束在 V0.1 全部启用")
            if key == "walk_group_admin_class_cap":
                if not isinstance(value, int) or value < 0 or value == 1:
                    errors.append("walk_group_admin_class_cap 必须是0（未启用）或>=2的整数")
            if key == "weights":
                if not isinstance(value, dict) or any(not isinstance(v, (int, float)) or v < 0 for v in value.values()):
                    errors.append("weights 必须是非负数值对象")
            if key == "time_limit_seconds" and (not isinstance(value, int) or value < 1 or value > 300):
                errors.append("time_limit_seconds 必须在1-300之间")
            if key == "num_workers" and (not isinstance(value, int) or value < 1 or value > 32):
                errors.append("num_workers 必须在1-32之间")
        if errors:
            raise HTTPException(422, "; ".join(errors))
        doc["rules"].update(body.values)
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.put("/api/scenarios/{sid}/course-config")
    def put_course_config(sid: str, body: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        errors = []
        cleaned: dict[str, list[dict[str, Any]]] = {}
        for subject, comps in body.items():
            if subject not in SUBJECTS:
                errors.append(f"未知科目: {subject}")
                continue
            total = 0
            clean_comps = []
            for c in comps:
                try:
                    hours = int(c.get("hours", 0))
                except (TypeError, ValueError):
                    errors.append(f"{subject} 的课时不是整数")
                    continue
                if hours < 0:
                    errors.append(f"{subject} 的课时不能为负")
                name = str(c.get("name", "")).strip()
                if not name:
                    errors.append(f"{subject} 存在空细分课程")
                clean_comps.append({"name": name, "hours": hours, "kind": c.get("kind", "lecture")})
                total += hours
            if total <= 0:
                errors.append(f"{subject} 的周课时必须大于0")
            cleaned[subject] = clean_comps
        if errors:
            raise HTTPException(422, "; ".join(errors))
        doc["course_config"].update(cleaned)
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.put("/api/scenarios/{sid}/time-model")
    def put_time_model(sid: str, body: dict[str, Any]) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        slots = body.get("slots")
        if not isinstance(slots, list) or len(slots) != 42:
            raise HTTPException(422, "time_model.slots 必须包含42个网格时段")
        active = [s for s in slots if s.get("active")]
        if len(active) != 31:
            raise HTTPException(422, f"必须有31个教学时段，当前{len(active)}个")
        phases = {"base": 0, "foreign": 0, "elective": 0}
        bands = {"first": 0, "second_a": 0, "second_b": 0}
        clean = []
        idx = 0
        seen = set()
        for s in sorted(slots, key=lambda x: (x.get("day_index", 0), x.get("period", 0))):
            key = (s.get("day_index"), s.get("period"))
            if key in seen:
                raise HTTPException(422, "时段重复")
            seen.add(key)
            phase = s.get("phase")
            band = s.get("band")
            if s.get("active"):
                if phase not in phases:
                    raise HTTPException(422, "启用时段的 phase 必须是 base/foreign/elective")
                phases[phase] += 1
                if phase == "elective":
                    if band not in bands:
                        raise HTTPException(422, "走班时段 band 必须是 first/second_a/second_b")
                    bands[band] += 1
                else:
                    band = phase
                index = idx
                idx += 1
            else:
                phase, band, index = None, None, -1
            clean.append({
                **s, "phase": phase, "band": band, "index": index,
                "active": bool(s.get("active")),
                "activity": s.get("activity") or ("上课" if s.get("active") else "非教学"),
            })
        if phases["base"] < 13 or phases["foreign"] < 6 or any(v < 4 for v in bands.values()):
            raise HTTPException(
                422,
                f"时段数量不足：base={phases['base']}/13, foreign={phases['foreign']}/6, "
                f"走班段={bands}/每段4",
            )
        doc["time_model"]["slots"] = clean
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    @app.patch("/api/scenarios/{sid}/teacher-bindings")
    def patch_teacher_bindings(sid: str, body: TeacherBindingsPatch) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        teachers = {t["id"]: t for t in doc["teachers"]}
        admins = {s["admin_class"] for s in doc["students"]}
        subjects = {"语文", "数学", "英语", "日语", "物理", "历史", "生物", "化学", "地理", "政治"}
        errors = []
        cleaned: dict[str, str] = {}
        for key, tid in body.bindings.items():
            parts = key.split("|")
            subject = parts[0]
            if subject not in subjects:
                errors.append(f"绑定键科目无效: {key}")
                continue
            if not tid:
                continue
            teacher = teachers.get(tid)
            if teacher is None:
                errors.append(f"教师不存在: {tid}")
                continue
            if subject not in (teacher.get("candidate_subjects") or [teacher["subject"]]):
                errors.append(f"{tid} 不是 {subject} 候选教师")
                continue
            if subject in ("语文", "数学") and len(parts) == 2 and parts[1] not in admins:
                errors.append(f"行政班不存在: {parts[1]}")
                continue
            cleaned[key] = tid
        if errors:
            raise HTTPException(422, "; ".join(errors))
        doc["teacher_bindings"] = cleaned
        save_doc(doc)
        return scenario_payload(get_doc_or_404(doc["id"]))

    # --------------------------------------------------------------------- solves
    @app.post("/api/scenarios/{sid}/solve")
    def solve(sid: str, body: SolveRequest | None = None) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        try:
            scenario = Scenario.from_dict(doc)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(422, f"场景数据无法加载：{exc}") from exc
        body = body or SolveRequest()
        result = run_scenario(
            scenario, time_limit_seconds=body.time_limit_seconds,
            num_workers=body.num_workers, weights=body.weights,
        )
        result["scenario_updated_at"] = doc["_updated_at"]
        result["is_stale"] = False
        db.save_run(result, doc["_updated_at"])
        return enrich_result(result, doc)

    @app.get("/api/scenarios/{sid}/runs")
    def runs(sid: str) -> list[dict[str, Any]]:
        doc = get_doc_or_404(sid)
        return db.list_runs(doc["id"])

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        result = db.get_run(run_id)
        if not result:
            raise HTTPException(404, "求解记录不存在")
        doc = get_doc_or_404(result["scenario_id"])
        result["is_stale"] = result.get("scenario_updated_at") != doc["_updated_at"]
        return enrich_result(result, doc)

    @app.post("/api/runs/{run_id}/validate")
    def revalidate(run_id: str) -> dict[str, Any]:
        result = db.get_run(run_id)
        if not result:
            raise HTTPException(404, "求解记录不存在")
        doc = get_doc_or_404(result["scenario_id"])
        report = validate_result(Scenario.from_dict(doc), result)
        result["validation"] = report
        db.save_run(result, result.get("scenario_updated_at", doc["_updated_at"]))
        return report

    @app.get("/api/runs/{run_id}/entities")
    def run_entities(run_id: str, view: str = Query("admin")) -> list[dict[str, Any]]:
        result = db.get_run(run_id)
        if not result:
            raise HTTPException(404, "求解记录不存在")
        doc = get_doc_or_404(result["scenario_id"])
        if view == "class":
            return [
                {"id": c["id"], "name": c["name"], "subject": c["subject"],
                 "size": c.get("size", len(c.get("student_ids", []))),
                 "teacher_id": c.get("teacher_id"), "room_id": c.get("room_id")}
                for c in result.get("classes", [])
            ]
        if view not in ("admin", "student", "teacher", "room"):
            raise HTTPException(422, "view 必须是 admin/student/teacher/room/class")
        return view_entities(doc, view)

    @app.get("/api/runs/{run_id}/timetable")
    def timetable(
        run_id: str, view: str = Query("admin"),
        entity_id: str | None = Query(None),
    ) -> dict[str, Any]:
        result = db.get_run(run_id)
        if not result:
            raise HTTPException(404, "求解记录不存在")
        doc = get_doc_or_404(result["scenario_id"])
        if view not in ("admin", "student", "teacher", "room", "class"):
            raise HTTPException(422, "view 必须是 admin/student/teacher/room/class")
        if not entity_id:
            entities = run_entities(run_id, view)
            if not entities:
                raise HTTPException(404, "没有可展示的对象")
            entity_id = entities[0]["id"]
        return build_timetable(doc, result, view, entity_id)

    @app.get("/api/runs/{run_id}/teaching-classes")
    def teaching_classes(run_id: str) -> list[dict[str, Any]]:
        result = db.get_run(run_id)
        if not result:
            raise HTTPException(404, "求解记录不存在")
        doc = get_doc_or_404(result["scenario_id"])
        teachers = {t["id"]: t["name"] for t in doc.get("teachers", [])}
        rooms = {r["id"]: r["name"] for r in doc.get("rooms", [])}
        out = []
        for c in result.get("classes", []):
            item = dict(c)
            item["teacher_name"] = teachers.get(c["teacher_id"], c["teacher_id"])
            item["room_name"] = rooms.get(c["room_id"], c["room_id"])
            item["student_count"] = len(c.get("student_ids", []))
            out.append(item)
        return out

    # -------------------------------------------------------------------- excel
    @app.get("/api/scenarios/{sid}/export.xlsx")
    def export_xlsx(sid: str, run_id: str | None = Query(None)) -> Response:
        doc = get_doc_or_404(sid)
        if run_id:
            result = db.get_run(run_id)
            if not result:
                raise HTTPException(404, "求解记录不存在")
        else:
            result = db.latest_run(doc["id"]) or {
                "status": "unsolved", "solver_status": "UNSOLVED",
                "status_zh": "尚未求解", "tasks": [], "classes": [],
                "validation": None, "metrics": {},
            }
        result = dict(result)
        result["is_stale"] = result.get("scenario_updated_at") != doc["_updated_at"]
        data = export_workbook(doc, result)
        filename = f"AI-WISH-001_{doc['id']}_课表.xlsx"
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )

    @app.get("/api/excel/template")
    def excel_template(sid: str = Query("F"), sheet: str | None = Query(None)) -> Response:
        doc = get_doc_or_404(sid)
        if sheet not in (None, "students", "teachers", "rooms", "courses"):
            raise HTTPException(422, "sheet 必须是 students/teachers/rooms/courses")
        data = template_workbook(doc, only_sheet=sheet)
        filename = f"AI-WISH-001_{doc['id']}_导入模板.xlsx"
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )

    @app.post("/api/scenarios/{sid}/import")
    async def import_excel(
        sid: str, file: UploadFile = File(...), mode: str = Query("replace"),
        sheet: str | None = Query(None),
    ) -> dict[str, Any]:
        doc = get_doc_or_404(sid)
        if mode not in ("replace", "merge"):
            raise HTTPException(422, "mode 必须是 replace 或 merge")
        if sheet not in (None, "all", "students", "teachers", "rooms", "courses"):
            raise HTTPException(422, "sheet 必须是 students/teachers/rooms/courses/all")
        content = await file.read()
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(413, "Excel 文件不得超过20MB")
        only = None if sheet in (None, "all") else sheet
        new_doc, errors, summary = import_workbook(content, doc, mode, only_sheet=only)
        if errors:
            return JSONResponse(status_code=422, content={"ok": False, "errors": errors[:50], "summary": summary})
        save_doc(new_doc)
        return {"ok": True, "summary": summary, "scenario": scenario_payload(get_doc_or_404(doc["id"]))}

    # ---------------------------------------------------------------- frontend
    # Standalone: dist at `/`.  DSH plugin mode: dist at `/app` and the host
    # plugin proxies `/plugins/aiwish/*` after stripping that prefix.
    dist = Path(os.environ.get("AIWISH_STATIC_DIR", str(ROOT / "frontend" / "dist")))
    static_prefix = os.environ.get("AIWISH_STATIC_PREFIX", "").rstrip("/")
    if dist.exists():
        if static_prefix:
            assets_dir = dist / "assets"
            if assets_dir.exists():
                app.mount(f"{static_prefix}/assets", StaticFiles(directory=assets_dir), name="assets")

            def _plugin_index(path: str = "") -> FileResponse:
                if path and ".." in path.split("/"):
                    raise HTTPException(404, "not found")
                target = (dist / path) if path else (dist / "index.html")
                if target.is_file():
                    return FileResponse(target)
                return FileResponse(dist / "index.html")

            app.add_api_route(static_prefix, _plugin_index, methods=["GET"])
            app.add_api_route(f"{static_prefix}/{{path:path}}", _plugin_index, methods=["GET"])
        else:
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

            @app.get("/")
            def index() -> FileResponse:
                return FileResponse(dist / "index.html")

            @app.get("/{path:path}")
            def spa(path: str) -> FileResponse:
                if path.startswith("api/"):
                    raise HTTPException(404, "API not found")
                target = dist / path
                if target.is_file():
                    return FileResponse(target)
                return FileResponse(dist / "index.html")

    return app


app = create_app()
