"""Command-line interface for the scheduling core.

Examples:
    PYTHONPATH=engine python -m aiwish.cli list
    PYTHONPATH=engine python -m aiwish.cli run F --out data/F_result.json
    PYTHONPATH=engine python -m aiwish.cli run F --time-limit 20
    PYTHONPATH=engine python -m aiwish.cli validate data/F_result.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .data_gen import build_all_scenarios, scenario_summaries
from .runner import run_scenario, validate_result


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aiwish", description="AI-WISH-001 排课核心 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出模拟场景")

    run_p = sub.add_parser("run", help="运行一个场景的完整求解与独立校验")
    run_p.add_argument("scenario", help="场景 A-G")
    run_p.add_argument("--time-limit", type=int, default=None)
    run_p.add_argument("--workers", type=int, default=None)
    run_p.add_argument("--out", type=str, default=None, help="可选：保存完整 JSON 结果")
    run_p.add_argument("--summary", action="store_true", help="只打印摘要")

    val_p = sub.add_parser("validate", help="对已保存的结果重新运行独立校验器")
    val_p.add_argument("result", help="run 命令输出的 JSON 文件")

    args = parser.parse_args(argv)
    scenarios = build_all_scenarios()

    if args.command == "list":
        _print_json(scenario_summaries())
        return 0

    if args.command == "run":
        key = args.scenario.upper()
        if key not in scenarios:
            print(f"未知场景: {key}", file=sys.stderr)
            return 2
        result = run_scenario(
            scenarios[key], time_limit_seconds=args.time_limit,
            num_workers=args.workers,
        )
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.summary:
            summary = {
                "scenario": key, "status": result["status"],
                "solver_status": result["solver_status"],
                "status_zh": result["status_zh"], "message": result["message"],
                "solve_seconds": result["solve_seconds"],
                "validation_passed": (result.get("validation") or {}).get("passed"),
                "metrics": result.get("metrics", {}),
                "validation_summary": (result.get("validation") or {}).get("summary"),
            }
            _print_json(summary)
        else:
            _print_json(result)
        return 0 if result["status"] == "solved" else 1

    if args.command == "validate":
        path = Path(args.result)
        result = json.loads(path.read_text(encoding="utf-8"))
        key = result.get("scenario_id", "")
        if key not in scenarios:
            print(f"结果中的场景 {key} 不存在", file=sys.stderr)
            return 2
        report = validate_result(scenarios[key], result)
        _print_json(report)
        return 0 if report.get("passed") else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
