from __future__ import annotations

import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.main import create_app


def make_client(tmp_path):
    return TestClient(create_app(tmp_path / "test.db"))


def test_health_and_scenarios(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/health").json()["ok"] is True
    rows = client.get("/api/scenarios").json()
    assert {r["id"] for r in rows} == set("ABCDEFG")
    detail = client.get("/api/scenarios/F").json()
    assert detail["analysis"]["combination_count"] == 24
    assert detail["time_model"]["slots"]


def test_solve_and_four_views(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/scenarios/F/solve", json={"time_limit_seconds": 20})
    assert r.status_code == 200
    run = r.json()
    assert run["status"] == "solved"
    assert run["validation"]["passed"] is True
    rid = run["run_id"]
    for view, expected_min in (("admin", 8), ("student", 320), ("teacher", 62), ("room", 26)):
        entities = client.get(f"/api/runs/{rid}/entities?view={view}").json()
        assert len(entities) >= expected_min
        tt = client.get(f"/api/runs/{rid}/timetable?view={view}&entity_id={entities[0]['id']}").json()
        assert len(tt["cells"]) == 42
        assert tt["task_count"] == 31 if view == "student" else tt["task_count"] >= 1
    # Four source views share the same task source; validator counts must agree.
    v = run["validation"]
    assert v["view_counts"]["teacher_entries"] == len(run["tasks"])
    assert v["view_counts"]["room_entries"] == len(run["tasks"])
    assert v["view_counts"]["student_entries"] == 9920


def test_excel_endpoints(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/scenarios/F/solve", json={"time_limit_seconds": 20})
    tpl = client.get("/api/excel/template?sid=F")
    assert tpl.status_code == 200
    assert tpl.content[:2] == b"PK"
    export = client.get("/api/scenarios/F/export.xlsx")
    assert export.status_code == 200
    assert len(export.content) > 100000
    wb = load_workbook(io.BytesIO(export.content))
    assert "行政班课表" in wb.sheetnames
    imported = client.post(
        "/api/scenarios/F/import?mode=replace",
        files={"file": ("roundtrip.xlsx", export.content,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["summary"]["students"] == 320


def test_invalid_edit_does_not_corrupt(tmp_path):
    client = make_client(tmp_path)
    r = client.patch("/api/scenarios/A/students/S001", json={"second_subjects": ["生物", "生物"]})
    assert r.status_code == 422
    r = client.patch("/api/scenarios/A/teachers/T-CN-01", json={"unavailable_slots": ["不存在"]})
    assert r.status_code == 422


def test_strict_cap_via_api_reports_infeasible(tmp_path):
    client = make_client(tmp_path)
    r = client.put("/api/scenarios/F/rules", json={"values": {"walk_group_admin_class_cap": 2}})
    assert r.status_code == 200
    solved = client.post("/api/scenarios/F/solve", json={"time_limit_seconds": 10}).json()
    assert solved["status"] == "infeasible"
    assert solved["solver_status"] == "PRECHECK_INFEASIBLE"
    assert solved["tasks"] == []
    # Reset restores a solvable scenario.
    client.post("/api/scenarios/F/reset")
    solved2 = client.post("/api/scenarios/F/solve", json={"time_limit_seconds": 20}).json()
    assert solved2["status"] == "solved"


def test_revalidate_and_time_model_roundtrip(tmp_path):
    client = make_client(tmp_path)
    run = client.post("/api/scenarios/A/solve", json={"time_limit_seconds": 10}).json()
    assert run["status"] == "solved"
    report = client.post(f"/api/runs/{run['run_id']}/validate")
    assert report.status_code == 200
    assert report.json()["passed"] is True
    doc = client.get("/api/scenarios/A").json()
    r = client.put("/api/scenarios/A/time-model", json={"slots": doc["time_model"]["slots"]})
    assert r.status_code == 200, r.text
    bad = client.put("/api/scenarios/A/time-model", json={"slots": doc["time_model"]["slots"][:35]})
    assert bad.status_code == 422


def test_teacher_binding_api(tmp_path):
    client = make_client(tmp_path)
    r = client.patch("/api/scenarios/A/teacher-bindings",
                     json={"bindings": {"语文|高一(1)班": "T-CN-03"}})
    assert r.status_code == 200
    assert r.json()["teacher_bindings"]["语文|高一(1)班"] == "T-CN-03"
    solved = client.post("/api/scenarios/A/solve", json={"time_limit_seconds": 10}).json()
    assert solved["status"] == "solved"
    cls = next(c for c in solved["classes"] if c["name"] == "语文·高一(1)班")
    assert cls["teacher_id"] == "T-CN-03"
    assert solved["validation"]["passed"]
    bad = client.patch("/api/scenarios/A/teacher-bindings",
                       json={"bindings": {"数学|高一(1)班": "T-CN-03"}})
    assert bad.status_code == 422


def test_hard_constraints_cannot_be_disabled(tmp_path):
    client = make_client(tmp_path)
    r = client.put("/api/scenarios/A/rules", json={"values": {"student_no_overlap": False}})
    assert r.status_code == 422
    r = client.put("/api/scenarios/A/rules", json={"values": {"enabled_hard_constraints": []}})
    assert r.status_code == 422
