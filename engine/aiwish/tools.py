"""Stable tool-facing facade for future DSH/adapter integration.

This is not a DSH plugin.  It is the pure-Python capability surface that a DSH
tool adapter (or any other client) can call without importing FastAPI, SQLite
or React.  Every function returns JSON-serialisable data.
"""
from __future__ import annotations

import copy
from typing import Any

from .analysis import analyze_doc
from .data_gen import build_all_scenarios, build_scenario, scenario_summaries
from .domain import (
    DEFAULT_RULES, Scenario, validate_scenario_shape,
)
from .runner import run_scenario, validate_result


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"name": "import_basic_data", "title": "导入基础数据",
     "description": "导入/合并学生、教师、教室和课程配置，返回校验后的场景。",
     "requires_confirmation": False},
    {"name": "analyze_selection", "title": "分析学生选科",
     "description": "统计选科组合、外语、行政班与教师容量预警。",
     "requires_confirmation": False},
    {"name": "get_rules", "title": "查询排课规则",
     "description": "返回硬约束、待确认规则和软约束权重。",
     "requires_confirmation": False},
    {"name": "update_rules", "title": "修改排课规则",
     "description": "参数校验后修改规则；重要变更必须先返回确认请求。",
     "requires_confirmation": True},
    {"name": "run_auto_schedule", "title": "执行自动排课",
     "description": "运行 CP-SAT，并返回可行/最优/无解/超时状态与独立校验。",
     "requires_confirmation": False},
    {"name": "get_schedule", "title": "查询排课结果",
     "description": "按任务、教学班或视图返回课表。",
     "requires_confirmation": False},
    {"name": "diagnose_conflicts", "title": "诊断排课冲突",
     "description": "重新运行独立校验器，返回违规明细与预检原因。",
     "requires_confirmation": False},
    {"name": "reschedule_partial", "title": "局部调课并重新求解",
     "description": "V0.1 仅预留接口；当前返回未支持说明。",
     "requires_confirmation": True},
    {"name": "export_timetable", "title": "导出课表",
     "description": "导出 JSON 任务/四类视图；Excel 由 Web 适配层生成。",
     "requires_confirmation": False},
]


class ToolInputError(ValueError):
    pass


def list_scenarios() -> list[dict[str, Any]]:
    return scenario_summaries()


def get_scenario(scenario_id: str) -> dict[str, Any]:
    scenarios = build_all_scenarios()
    if scenario_id.upper() not in scenarios:
        raise ToolInputError(f"未知场景: {scenario_id}")
    return scenarios[scenario_id.upper()].to_dict()


def import_basic_data(payload: dict[str, Any], base_scenario_id: str = "F") -> dict[str, Any]:
    """Replace/merge base data, validating every field.

    ``payload`` may contain scenario_id, students, teachers, rooms,
    course_config.  Existing scenario metadata is preserved when re-importing.
    """
    scenarios = build_all_scenarios()
    sid = str(payload.get("scenario_id") or base_scenario_id).upper()
    if sid not in scenarios:
        raise ToolInputError(f"未知场景: {sid}")
    doc = scenarios[sid].to_dict()
    for key in ("students", "teachers", "rooms", "course_config", "name", "notes"):
        if key in payload:
            doc[key] = payload[key]
    scenario = Scenario.from_dict(doc)
    errors = validate_scenario_shape(scenario)
    if errors:
        raise ToolInputError("；".join(errors))
    return scenario.to_dict()


def analyze_selection(scenario: Scenario | dict[str, Any]) -> dict[str, Any]:
    doc = scenario.to_dict() if isinstance(scenario, Scenario) else scenario
    return analyze_doc(doc)


def get_rules(scenario: Scenario | dict[str, Any]) -> dict[str, Any]:
    doc = scenario.to_dict() if isinstance(scenario, Scenario) else scenario
    return {
        "rules": copy.deepcopy({**DEFAULT_RULES, **(doc.get("rules") or {})}),
        "note": "硬约束默认全部启用；walk_group_admin_class_cap 是待确认规则，0 表示未启用。",
    }


def validate_rule_patch(current: dict[str, Any], patch: dict[str, Any]) -> list[str]:
    errors = []
    allowed = set(DEFAULT_RULES) | {"weights", "time_limit_seconds", "num_workers", "random_seed"}
    boolean_keys = {k for k, v in DEFAULT_RULES.items() if isinstance(v, bool)}
    for key, value in patch.items():
        if key not in allowed and key not in current:
            errors.append(f"未知规则: {key}")
            continue
        if key in boolean_keys:
            if not isinstance(value, bool):
                errors.append(f"{key} 必须是布尔值")
            elif value is not True:
                errors.append(f"{key} 是 V0.1 固定硬约束，不允许关闭")
        if key == "enabled_hard_constraints":
            errors.append("enabled_hard_constraints 为只读字段；硬约束在 V0.1 全部启用")
        if key == "walk_group_admin_class_cap" and (not isinstance(value, int) or value < 0 or value == 1):
            errors.append("walk_group_admin_class_cap 必须是0或>=2的整数")
        if key == "weights":
            if not isinstance(value, dict) or any(not isinstance(v, (int, float)) or v < 0 for v in value.values()):
                errors.append("weights 必须是非负数值对象")
        if key == "time_limit_seconds" and (not isinstance(value, int) or not 1 <= value <= 300):
            errors.append("time_limit_seconds 必须在1-300")
        if key == "num_workers" and (not isinstance(value, int) or not 1 <= value <= 32):
            errors.append("num_workers 必须在1-32")
    return errors


def update_rules(
    scenario: Scenario | dict[str, Any],
    patch: dict[str, Any],
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Apply a validated rule patch, but require explicit confirmation first.

    Returns a proposal when ``confirmed`` is false.  This is the guard required
    before a natural-language or agent-initiated change is applied.
    """
    doc = scenario.to_dict() if isinstance(scenario, Scenario) else copy.deepcopy(scenario)
    current = {**DEFAULT_RULES, **(doc.get("rules") or {})}
    errors = validate_rule_patch(current, patch)
    if errors:
        return {"ok": False, "requires_confirmation": False, "errors": errors}
    important = {k: v for k, v in patch.items() if k in {
        "walk_group_admin_class_cap", "enabled_hard_constraints", "weights",
    }}
    if important and not confirmed:
        return {
            "ok": False,
            "requires_confirmation": True,
            "proposal": important,
            "message": "规则变更会影响排课结果，请确认后再应用。",
        }
    current.update(patch)
    doc["rules"] = current
    updated = Scenario.from_dict(doc)
    return {
        "ok": True, "requires_confirmation": False,
        "scenario": updated.to_dict(), "applied": patch,
    }


def run_auto_schedule(
    scenario: Scenario | dict[str, Any],
    *,
    time_limit_seconds: int | None = None,
    num_workers: int | None = None,
) -> dict[str, Any]:
    sc = scenario if isinstance(scenario, Scenario) else Scenario.from_dict(scenario)
    return run_scenario(sc, time_limit_seconds=time_limit_seconds, num_workers=num_workers)


def get_schedule(scenario: Scenario | dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "solver_status": result.get("solver_status"),
        "message": result.get("message"),
        "metrics": result.get("metrics", {}),
        "classes": result.get("classes", []),
        "tasks": result.get("tasks", []),
        "validation": result.get("validation"),
    }


def diagnose_conflicts(scenario: Scenario | dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("tasks"):
        return {
            "passed": False,
            "message": result.get("message", "没有课表任务"),
            "precheck": result.get("precheck"),
            "violations": [],
        }
    sc = scenario if isinstance(scenario, Scenario) else Scenario.from_dict(scenario)
    report = validate_result(sc, result)
    return {
        "passed": report.get("passed"),
        "violations": report.get("violations", []),
        "summary": report.get("summary", {}),
        "warnings": report.get("warnings", []),
    }


def reschedule_partial(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {
        "supported": False,
        "requires_confirmation": True,
        "message": "局部调课与增量重求解属于下一阶段能力，V0.1 尚未实现，不能伪造结果。",
    }


def export_timetable(result: dict[str, Any], view: str = "all") -> dict[str, Any]:
    tasks = result.get("tasks", [])
    if view == "all":
        return {"run_id": result.get("run_id"), "tasks": tasks, "classes": result.get("classes", [])}
    if view not in ("admin", "student", "teacher", "room"):
        raise ToolInputError("view 必须是 admin/student/teacher/room/all")
    return {
        "run_id": result.get("run_id"), "view": view,
        "entries": [
            {
                "task_id": t["id"], "day": t["day"], "period": t["period"],
                "subject": t["subject"], "class_name": t["class_name"],
                "teacher_id": t["teacher_id"], "room_id": t["room_id"],
                "admin_classes": t["admin_classes"], "student_ids": t["student_ids"],
            }
            for t in tasks
        ],
    }


def describe_tools() -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "tools": TOOL_SCHEMAS,
        "privacy": "所有学生/教师个人信息默认仅在本机处理；这些函数不调用任何远程大模型。",
        "natural_language_rule_flow": [
            "调用方把自然语言解析为结构化 rule patch（可选用本机或已授权模型）",
            "update_rules(... confirmed=False) 做参数校验并返回确认请求",
            "用户确认后，调用 update_rules(... confirmed=True) 应用",
        ],
    }
