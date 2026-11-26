"""One-call engine facade used by the CLI, FastAPI and future DSH tools."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .builder import PlanBuilder, PlanningError
from .domain import STATUS_ZH, Scenario, validate_scenario_shape
from .solver import SolveOptions, SolverInputError, solve_plan
from .validator import validate_schedule

INFEASIBLE_PRECHECK_CODES = {
    "capacity_conflict", "teacher_capacity", "teacher_availability",
    "walk_cap_teacher_conflict", "room_conflict",
}
MODEL_ERROR_CODES = {
    "teacher_missing", "config_error", "time_pool", "room_capacity",
    "student_load", "empty_plan",
}


def run_scenario(
    scenario: Scenario,
    *,
    time_limit_seconds: int | None = None,
    num_workers: int | None = None,
    weights: dict[str, float] | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    run_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    shape_errors = validate_scenario_shape(scenario)
    base_result: dict[str, Any] = {
        "run_id": run_id,
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "seed": scenario.seed,
        "created_at": created,
        "classes": [],
        "tasks": [],
        "pools": {},
        "diagnostics": [],
        "validation": None,
        "build_seconds": 0.0,
        "solve_seconds": 0.0,
        "total_seconds": 0.0,
        "assumptions": scenario.assumption_tags,
    }
    if shape_errors:
        base_result.update({
            "status": "error", "solver_status": "MODEL_INVALID",
            "status_zh": STATUS_ZH["MODEL_INVALID"],
            "message": "数据校验失败，未进入求解：" + "；".join(shape_errors[:8]),
            "errors": shape_errors,
        })
        base_result["total_seconds"] = round(time.perf_counter() - started, 3)
        return base_result

    build_started = time.perf_counter()
    try:
        plan = PlanBuilder(scenario).build()
    except PlanningError as exc:
        base_result["build_seconds"] = round(time.perf_counter() - build_started, 3)
        if exc.code in INFEASIBLE_PRECHECK_CODES:
            status = "infeasible"
            status_code = "PRECHECK_INFEASIBLE"
            message = f"数据预检证明无解：{exc.message}"
        else:
            status = "error"
            status_code = "MODEL_INVALID"
            message = f"模型/数据错误：{exc.message}"
        base_result.update({
            "status": status, "solver_status": status_code,
            "status_zh": STATUS_ZH.get(status_code, status_code),
            "message": message,
            "precheck": {"code": exc.code, "details": exc.details},
            "total_seconds": round(time.perf_counter() - started, 3),
        })
        return base_result
    base_result["build_seconds"] = round(time.perf_counter() - build_started, 3)
    options = SolveOptions(
        time_limit_seconds=int(time_limit_seconds or scenario.rules.get("time_limit_seconds", 30)),
        num_workers=int(num_workers or scenario.rules.get("num_workers", 8)),
        random_seed=int(scenario.rules.get("random_seed", scenario.seed)),
        weights=weights or scenario.rules.get("weights", {}),
    )
    try:
        solved = solve_plan(plan, options)
    except SolverInputError as exc:
        base_result.update({
            "status": "error", "solver_status": "MODEL_INVALID",
            "status_zh": STATUS_ZH["MODEL_INVALID"],
            "message": f"模型/数据错误：{exc}",
            "total_seconds": round(time.perf_counter() - started, 3),
        })
        return base_result

    base_result.update({
        "status": solved["status"],
        "solver_status": solved["solver_status"],
        "status_zh": solved["status_zh"],
        "message": solved["message"],
        "solve_seconds": solved["solve_seconds"],
        "objective_value": solved["objective_value"],
        "model_stats": {
            "variables": solved["variables"], "constraints": solved["constraints"],
            "hints": solved["hint_count"],
        },
        "classes": [c.to_dict() for c in plan.classes],
        "tasks": solved["tasks"],
        "pools": plan.pools,
        "diagnostics": plan.diagnostics,
        "metrics": solved["metrics"],
        "solve_options": {
            "time_limit_seconds": options.time_limit_seconds,
            "num_workers": options.num_workers,
            "random_seed": options.random_seed,
            "weights": options.weights,
        },
    })
    if solved["status"] == "solved" and validate:
        base_result["validation"] = validate_schedule(
            scenario, base_result["classes"], base_result["tasks"]
        )
    base_result["total_seconds"] = round(time.perf_counter() - started, 3)
    return base_result


def validate_result(scenario: Scenario, result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("tasks"):
        return {
            "passed": False, "summary": {"hard_constraint_violations": 1, "passed": False},
            "violations": [{
                "code": "no_schedule", "category": "structure",
                "scope": "result", "message": "该结果没有可校验的课表任务",
            }],
            "violation_counts": {"no_schedule": 1}, "warnings": [],
            "checked": {"tasks": 0}, "view_counts": {},
        }
    return validate_schedule(scenario, result.get("classes", []), result["tasks"])
