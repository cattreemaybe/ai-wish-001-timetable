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


def test_custom_scenario_and_preflight(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/scenarios/custom", json={"name": "我的学校"})
    assert r.status_code == 200
    doc = r.json()
    sid = doc["id"]
    assert doc["is_sample"] is False
    assert doc["students"] == []
    listed = {x["id"]: x for x in client.get("/api/scenarios").json()}
    assert listed[sid]["name"] == "我的学校"
    assert listed[sid]["is_sample"] is False
    pre = client.get(f"/api/scenarios/{sid}/preflight").json()
    assert pre["ready"] is False
    assert pre["status"] == "blocked"
    assert {i["key"] for i in pre["items"]} >= {"students", "teachers", "rooms", "courses", "time", "rules"}
    # Manual add
    assert client.post(f"/api/scenarios/{sid}/students", json={
        "name": "张三", "admin_class": "高一(1)班", "language": "英语",
        "first_subject": "物理", "second_subjects": ["生物", "化学"],
    }).status_code == 200
    assert client.post(f"/api/scenarios/{sid}/teachers", json={
        "name": "王老师", "subject": "语文",
    }).status_code == 200
    assert client.post(f"/api/scenarios/{sid}/rooms", json={
        "name": "A101", "capacity": 50,
    }).status_code == 200
    after = client.get(f"/api/scenarios/{sid}").json()
    assert len(after["students"]) == 1
    assert len(after["teachers"]) == 1
    assert len(after["rooms"]) == 1


def test_per_sheet_import_does_not_overwrite_other_categories(tmp_path):
    from aiwish.data_gen import build_all_scenarios
    from app.excel_io import template_workbook

    client = make_client(tmp_path)
    sid = client.post("/api/scenarios/custom", json={"name": "分项导入"}).json()["id"]
    source = build_all_scenarios()["F"].to_dict()
    for sheet in ("students", "teachers", "rooms"):
        data = template_workbook(source, only_sheet=sheet)
        r = client.post(
            f"/api/scenarios/{sid}/import?mode=replace&sheet={sheet}",
            files={"file": (f"{sheet}.xlsx", data,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 200, r.text
        current = client.get(f"/api/scenarios/{sid}").json()
        assert len(current["students"]) == (2 if sheet == "students" else current["students"].__len__())
        if sheet == "students":
            assert len(current["teachers"]) == 0
            assert len(current["rooms"]) == 0
        if sheet == "teachers":
            assert len(current["teachers"]) == 2
            assert len(current["rooms"]) == 0
        if sheet == "rooms":
            assert len(current["rooms"]) == 2
    # courses only should leave the other lists intact
    data = template_workbook(source, only_sheet="courses")
    r = client.post(
        f"/api/scenarios/{sid}/import?mode=replace&sheet=courses",
        files={"file": ("courses.xlsx", data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200
    current = client.get(f"/api/scenarios/{sid}").json()
    assert len(current["students"]) == 2
    assert len(current["teachers"]) == 2
    assert len(current["rooms"]) == 2
    assert len(current["course_config"]) >= 10


def test_preflight_blocks_resource_shortage(tmp_path):
    client = make_client(tmp_path)
    pre = client.get("/api/scenarios/G/preflight").json()
    assert pre["ready"] is False
    assert "资源" in pre["message"]


def test_sheet_templates_are_scoped(tmp_path):
    from openpyxl import load_workbook
    import io
    client = make_client(tmp_path)
    r = client.get("/api/excel/template?sid=F&sheet=students")
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content), data_only=True)
    assert "学生" in wb.sheetnames
    assert "教师" not in wb.sheetnames
    assert "课程配置" not in wb.sheetnames


def test_import_feedback_reports_duplicates_and_missing(tmp_path):
    from aiwish.data_gen import build_all_scenarios
    from app.excel_io import template_workbook
    from openpyxl import load_workbook
    import io
    client = make_client(tmp_path)
    sid = client.post("/api/scenarios/custom", json={"name": "反馈测试"}).json()["id"]
    source = build_all_scenarios()["F"].to_dict()
    data = template_workbook(source, only_sheet="students")
    wb = load_workbook(io.BytesIO(data))
    ws = wb["学生"]
    # Keep two rows but duplicate the first student id.
    ws.cell(row=3, column=1, value=ws.cell(row=2, column=1).value)
    buf = io.BytesIO(); wb.save(buf)
    r = client.post(
        f"/api/scenarios/{sid}/import?mode=merge&sheet=students",
        files={"file": ("dup.xlsx", buf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert summary["duplicates"]
    assert summary["students"] == 1
    # Missing name should fail without writing.
    data = template_workbook(source, only_sheet="students")
    wb = load_workbook(io.BytesIO(data))
    wb["学生"].cell(row=2, column=2, value="")
    buf = io.BytesIO(); wb.save(buf)
    r = client.post(
        f"/api/scenarios/{sid}/import?mode=merge&sheet=students",
        files={"file": ("missing.xlsx", buf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 422
    assert r.json()["summary"]["failed_rows"] >= 1
    assert len(client.get(f"/api/scenarios/{sid}").json()["students"]) == 1
