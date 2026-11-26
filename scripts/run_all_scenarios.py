"""Reproduce the scenario test table used in TEST_REPORT.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from aiwish.data_gen import build_all_scenarios  # noqa: E402
from aiwish.runner import run_scenario  # noqa: E402

rows = []
for key in "ABCDEFG":
    result = run_scenario(build_all_scenarios()[key], time_limit_seconds=30)
    validation = result.get("validation") or {}
    rows.append({
        "scenario": key,
        "status": result["solver_status"],
        "status_zh": result["status_zh"],
        "solve_seconds": result["solve_seconds"],
        "teaching_classes": len(result.get("classes", [])),
        "tasks": len(result.get("tasks", [])),
        "validation_passed": validation.get("passed"),
        "walking_students": result.get("metrics", {}).get("walking_student_count"),
        "merged_classes": result.get("metrics", {}).get("merged_class_count"),
        "message": result["message"],
    })
print(json.dumps(rows, ensure_ascii=False, indent=2))
