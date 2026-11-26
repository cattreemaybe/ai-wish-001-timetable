# 示例数据与产物

本目录包含运行时数据库和可选示例文件。它们是生成物，不是算法输入的一部分；场景数据由 `engine/aiwish/data_gen.py` 固定种子生成。

| 文件 | 说明 |
|---|---|
| `aiwish.db` | 本地 SQLite：场景快照与运行记录；首次启动会自动创建 |
| `AI-WISH-001_基础数据导入模板.xlsx` | 可直接填写/导入的 Excel 模板 |
| `AI-WISH-001_F_课表.xlsx` | F 场景示例导出，含四类课表与校验结果 |
| `F_result.json` | F 场景完整求解结果快照，可用于 CLI 校验 |

重新生成：

```bash
# Excel
curl -s 'http://127.0.0.1:8000/api/scenarios/F/export.xlsx' -o data/F.xlsx

# JSON
PYTHONPATH=engine .venv/bin/python -m aiwish.cli run F --out data/F_result.json
```

删除 `aiwish.db` 后重启会自动重建 A-G 场景，但不会保留历史运行记录。
