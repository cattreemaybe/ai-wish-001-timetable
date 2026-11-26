"""SQLite persistence for scenarios and solve runs.

Scenario payloads are JSON documents.  Keeping snapshots in SQLite makes the
prototype fully local and avoids a migration-heavy schema in V0.1.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiwish.data_gen import build_all_scenarios

_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self) -> None:
        with _LOCK, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scenarios (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    solver_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    scenario_updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_scenario ON runs(scenario_id, created_at DESC)")
            conn.execute("CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.commit()
            # Seed only when missing; user edits survive restarts.
            existing = {r["id"] for r in conn.execute("SELECT id FROM scenarios")}
            for sid, scenario in build_all_scenarios().items():
                if sid not in existing:
                    conn.execute(
                        "INSERT INTO scenarios(id, payload, updated_at) VALUES (?, ?, ?)",
                        (sid, json.dumps(scenario.to_dict(), ensure_ascii=False), _now()),
                    )
            conn.commit()

    # --------------------------------------------------------------- scenarios
    def list_scenarios(self) -> list[dict[str, Any]]:
        with _LOCK, self._connect() as conn:
            rows = conn.execute("SELECT id, updated_at FROM scenarios ORDER BY id").fetchall()
            return [{"id": r["id"], "updated_at": r["updated_at"]} for r in rows]

    def get_scenario_doc(self, sid: str) -> dict[str, Any] | None:
        with _LOCK, self._connect() as conn:
            row = conn.execute(
                "SELECT payload, updated_at FROM scenarios WHERE id = ?", (sid,)
            ).fetchone()
            if not row:
                return None
            data = json.loads(row["payload"])
            data.setdefault("teacher_bindings", {})
            data["_updated_at"] = row["updated_at"]
            return data

    def save_scenario_doc(self, sid: str, data: dict[str, Any]) -> str:
        payload = {k: v for k, v in data.items() if not k.startswith("_")}
        ts = _now()
        with _LOCK, self._connect() as conn:
            conn.execute(
                "INSERT INTO scenarios(id, payload, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (sid, json.dumps(payload, ensure_ascii=False), ts),
            )
            conn.commit()
        return ts

    def reset_scenario(self, sid: str) -> dict[str, Any] | None:
        scenarios = build_all_scenarios()
        if sid not in scenarios:
            return None
        doc = scenarios[sid].to_dict()
        ts = self.save_scenario_doc(sid, doc)
        doc["_updated_at"] = ts
        return doc

    # -------------------------------------------------------------------- runs
    def save_run(self, result: dict[str, Any], scenario_updated_at: str) -> None:
        with _LOCK, self._connect() as conn:
            conn.execute(
                "INSERT INTO runs(id, scenario_id, status, solver_status, created_at, "
                "scenario_updated_at, payload) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
                "solver_status=excluded.solver_status, scenario_updated_at=excluded.scenario_updated_at, "
                "payload=excluded.payload",
                (
                    result["run_id"], result["scenario_id"], result["status"],
                    result["solver_status"], result["created_at"],
                    scenario_updated_at,
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with _LOCK, self._connect() as conn:
            row = conn.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            return json.loads(row["payload"])

    def list_runs(self, sid: str, limit: int = 20) -> list[dict[str, Any]]:
        with _LOCK, self._connect() as conn:
            scenario = conn.execute(
                "SELECT updated_at FROM scenarios WHERE id = ?", (sid,)
            ).fetchone()
            rows = conn.execute(
                "SELECT id, status, solver_status, created_at, scenario_updated_at, payload "
                "FROM runs WHERE scenario_id = ? ORDER BY created_at DESC LIMIT ?",
                (sid, limit),
            ).fetchall()
            out = []
            for r in rows:
                payload = json.loads(r["payload"])
                out.append({
                    "run_id": r["id"], "status": r["status"],
                    "solver_status": r["solver_status"],
                    "created_at": r["created_at"],
                    "is_stale": bool(scenario and r["scenario_updated_at"] != scenario["updated_at"]),
                    "solve_seconds": payload.get("solve_seconds", 0),
                    "message": payload.get("message", ""),
                    "metrics": payload.get("metrics", {}),
                    "validation_passed": (payload.get("validation") or {}).get("passed"),
                })
            return out

    def latest_run(self, sid: str) -> dict[str, Any] | None:
        with _LOCK, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM runs WHERE scenario_id = ? ORDER BY created_at DESC LIMIT 1",
                (sid,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["payload"])

    def set_state(self, key: str, value: str) -> None:
        with _LOCK, self._connect() as conn:
            conn.execute(
                "INSERT INTO app_state(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value),
            )
            conn.commit()

    def get_state(self, key: str, default: str | None = None) -> str | None:
        with _LOCK, self._connect() as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
