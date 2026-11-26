from __future__ import annotations

from openpyxl import load_workbook
import io

from app.excel_io import export_workbook, import_workbook, template_workbook


def test_export_contains_all_views(scenarios, solved_f):
    data = export_workbook(scenarios["F"].to_dict(), solved_f)
    wb = load_workbook(io.BytesIO(data), data_only=True)
    for name in ("总览", "学生选科", "教师资源", "课程配置", "教室资源", "教学班",
                 "行政班课表", "学生课表", "教师课表", "教室课表", "校验结果"):
        assert name in wb.sheetnames
    assert wb["学生选科"].max_row >= 321
    assert wb["校验结果"]["B4"].value is not None


def test_template_has_expected_headers(scenarios):
    data = template_workbook(scenarios["F"].to_dict())
    wb = load_workbook(io.BytesIO(data), data_only=True)
    assert [c.value for c in wb["学生"][1]][:4] == ["学号", "姓名", "行政班", "外语"]
    assert wb["课程配置"].max_row >= 20


def test_export_import_roundtrip(scenarios, solved_f):
    doc = scenarios["F"].to_dict()
    data = export_workbook(doc, solved_f)
    new_doc, errors, summary = import_workbook(data, doc, "replace")
    assert errors == []
    assert summary["students"] == 320
    assert summary["teachers"] == 62
    assert summary["rooms"] == 26
    assert len(new_doc["students"]) == 320
    assert len(new_doc["course_config"]) >= 10


def test_import_rejects_bad_combination(scenarios):
    doc = scenarios["A"].to_dict()
    data = template_workbook(doc)
    wb = load_workbook(io.BytesIO(data))
    ws = wb["学生"]
    # Same second-choice subject twice -> must be rejected.
    ws.cell(row=2, column=6, value="生物")
    ws.cell(row=2, column=7, value="生物")
    buf = io.BytesIO()
    wb.save(buf)
    new_doc, errors, summary = import_workbook(buf.getvalue(), doc, "replace")
    assert errors
    assert any("再选科目无效" in e for e in errors)
    assert new_doc == doc
