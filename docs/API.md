# API 速查

服务默认 `http://127.0.0.1:8000`。交互式文档：`/docs`。

## 健康与元数据

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/meta` | 版本、状态语义、假设摘要 |
| GET | `/api/scenarios` | 场景列表 |
| GET | `/api/scenarios/{sid}` | 场景详情 + 分析 + 最近运行 |

## 求解

```http
POST /api/scenarios/F/solve
Content-Type: application/json

{"time_limit_seconds": 30, "num_workers": 8}
```

返回完整结果，包括 `solver_status`、`tasks`、`classes`、`metrics`、`validation`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/scenarios/{sid}/runs` | 运行历史 |
| GET | `/api/runs/{run_id}` | 完整结果 |
| POST | `/api/runs/{run_id}/validate` | 重新运行独立校验 |
| GET | `/api/runs/{run_id}/entities?view=admin` | 视图对象列表 |
| GET | `/api/runs/{run_id}/timetable?view=student&entity_id=S001` | 单个视图 |
| GET | `/api/runs/{run_id}/teaching-classes` | 教学班列表 |

`view` 可选：`admin / student / teacher / room / class`。

## 编辑

| 方法 | 路径 | Body |
|---|---|---|
| PATCH | `/api/scenarios/{sid}/students/{student_id}` | `language`, `first_subject`, `second_subjects`, `admin_class` |
| PATCH | `/api/scenarios/{sid}/teachers/{teacher_id}` | `unavailable_slots`, `max_weekly_periods` |
| PATCH | `/api/scenarios/{sid}/rooms/{room_id}` | `capacity`, `name`, `building` |
| PUT | `/api/scenarios/{sid}/course-config` | 完整课程配置对象 |
| PUT | `/api/scenarios/{sid}/rules` | `{"values": {...}}` |
| PATCH | `/api/scenarios/{sid}/teacher-bindings` | `{"bindings": {...}}` |
| PUT | `/api/scenarios/{sid}/time-model` | `{"slots": [42 个网格]}` |
| POST | `/api/scenarios/{sid}/reset` | 恢复默认 A-G 场景 |

教师绑定示例：

```json
{"bindings": {"语文|高一(1)班": "T-CN-03", "数学|高一(1)班": "T-MA-02"}}
```

## Excel

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/excel/template?sid=F` | 导入模板 |
| POST | `/api/scenarios/{sid}/import?mode=replace` | multipart `file` |
| GET | `/api/scenarios/{sid}/export.xlsx` | 当前场景 + 最近课表 + 校验 |

## 错误语义

- `422`：参数/数据非法，未写入。
- `404`：场景/运行不存在。
- 求解状态在响应体，不用 HTTP 500 表示“无解”。

## CLI

```bash
PYTHONPATH=engine .venv/bin/python -m aiwish.cli list
PYTHONPATH=engine .venv/bin/python -m aiwish.cli run F --summary
PYTHONPATH=engine .venv/bin/python -m aiwish.cli run F --out data/F_result.json
PYTHONPATH=engine .venv/bin/python -m aiwish.cli validate data/F_result.json
```
