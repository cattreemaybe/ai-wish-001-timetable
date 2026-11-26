# AGENTS.md · 工程约定

本仓库是 AI-WISH-001 V0.1。任何自动化编码 Agent 接手前先读：

1. `README.md`
2. `REQUIREMENTS.md`
3. `ASSUMPTIONS.md`
4. `TEST_REPORT.md`
5. 本文件

## 1. 不可违反的原则

- **不得伪造课表**：课表必须来自 `engine/aiwish/solver.py` 的 CP-SAT 结果。
- **不得为了方便静默放宽硬约束**：学生/教师/教室冲突、课时、容量、教师不可排、时段、数学交替、走班结构都必须保留。
- **不得把超时当无解**：`UNKNOWN` 必须保持 `UNKNOWN`。
- **不得让校验器依赖求解器**：`validator.py` 不允许 import `solver.py` 或 `builder.py`。
- **不得把个人信息发远程模型**：本项目默认本地；未来 DSH 适配也要遵守。
- **需求未确认的规则**：写进 `ASSUMPTIONS.md`，做成可配置项，默认值要说明理由。
- **发现需求/资源冲突**：如实报告并写测试；不要通过改数据掩盖。

## 2. 目录边界

```text
engine/aiwish/     纯 Python 核心，不得 import fastapi/sqlite3/react
backend/app/       Web/DB/Excel 适配，不得自己计算课表
frontend/          React，不得假设后端未返回的数据
dsh-plugin/        DSH 宿主/客户端/打包脚本，不得复制排课算法
dist/              平台 tgz 与 ZIP 分发包装
docs/              方案与截图
```

### 依赖方向

```text
frontend -> backend -> engine
                 \-> excel_io -> engine
engine/tools.py -> engine only
```

`engine` 不依赖 `backend`。`backend` 通过 `run_scenario`、`validate_schedule`、`analyze_doc`、`tools.py` 调用核心。

## 3. 常用命令

```bash
# DSH 插件构建（先构建前端，再准备平台 runtime）
cd frontend && pnpm run build
cd ..
.venv/bin/python dsh-plugin/packaging/stage.py --platform darwin --python-source /path/to/runtime --out dist/dsh-aiwish-timetable-darwin

# 隔离 DSH 安装测试
DSH_HOME=/tmp/dsh-test dsh --profile aiwish --from-default-profile web --dump-config
DSH_HOME=/tmp/dsh-test dsh plugin --profile aiwish add ./dist/...tgz
DSH_HOME=/tmp/dsh-test dsh --profile aiwish --port 8012 --no-open
```

```bash
# 安装 / 启动
./start.sh
./dev.sh

# 测试
PYTHONPATH=engine:backend .venv/bin/pytest
./test.sh

# 前端
cd frontend && pnpm run build
cd frontend && pnpm run typecheck

# 核心 CLI
PYTHONPATH=engine .venv/bin/python -m aiwish.cli run F --summary
PYTHONPATH=engine .venv/bin/python scripts/run_all_scenarios.py
```

注意：本机 `python3` 可能指向 SSL 损坏的 conda。使用项目 `.venv` 或 `/opt/homebrew/bin/python3`。`start.sh` 会自动处理。

## 4. 数据模型不变量

- 31 个 active slot；42 个网格格。
- 每名学生每周 31 个任务（当前场景）。
- 每个任务恰好一个 slot。
- 学生每 slot 恰好 1 个任务（31/31 模型）。
- 教师每 slot ≤1；教室每 slot ≤1。
- 同一教学班同一天同科 ≤2。
- 数学 8 任务严格 `L,P,L,P,L,P,L,P` 时间递增。
- 首选段只有物理/历史；外语段只有英语/日语；再选每段≤3科。
- 教学班固定教师、固定教室。

修改任何一条都必须同步更新：

- `engine/aiwish/builder.py`
- `engine/aiwish/solver.py`
- `engine/aiwish/validator.py`
- `ASSUMPTIONS.md`
- 测试
- README 中的结果表

## 5. 添加规则

1. 在 `domain.DEFAULT_RULES` 加默认值。
2. 在 `backend/app/main.py` 的 `patch_rules` 白名单/校验中加入。
3. 若影响求解，在 `solver.py` 加约束。
4. 在 `validator.py` 独立复核。
5. 在 `engine/tools.py` 的 `validate_rule_patch` 加校验（如适用）。
6. 加测试：通过、违规、规则关闭语义。
7. 在 `ASSUMPTIONS.md` 写来源与假设。

不要只改前端开关。

## 6. 添加场景

1. 在 `engine/aiwish/data_gen.py` 的 `_scenario_specs()` 加 spec。
2. 确保固定 seed。
3. 不写死课表；只生成学生/教师/教室/规则。
4. 加测试。
5. 更新 README 场景表与 TEST_REPORT。
6. 如果是“无解场景”，必须说明是预检、CP-SAT 还是数据错误，并断言不是 `UNKNOWN`。

## 7. 前端约定

- API 客户端集中在 `frontend/src/api.ts`。
- 全局场景/运行状态在 `frontend/src/context.tsx`。
- 页面不要直接 fetch，优先走 `api`。
- 中文文案；状态必须显示真实 `solver_status`。
- 编辑后旧课表必须显示“数据已修改 / 待重算”，不能继续冒充新结果。
- 课表组件支持同格多个教学班（走班）。
- 任何新页面要跑：

```bash
cd frontend && pnpm run build
```

并用浏览器巡检 console error。

## 8. API 约定

- `POST /api/scenarios/{id}/solve` 调用 `run_scenario`。
- 求解结果存 SQLite；`GET /api/runs/{id}` 返回完整快照。
- 编辑基础数据后，`updated_at` 变化，最新运行 `is_stale=true`。
- 重新校验使用 `POST /api/runs/{id}/validate`；DB 写入必须 upsert。
- 导出必须包含四类课表与校验；导入失败不能修改场景。

## 9. Excel 约定

- 模板表头在第 1 行；导出表头在第 3 行。导入器两种都接受。
- 导入严格校验学生组合、教师科目、教室容量、课程课时。
- 导出/导入往返是回归测试，不要破坏。

## 10. 测试要求

最低要求：

- 所有 A-F 场景可解且校验通过。
- G 预检无解且无任务。
- cap=2 的 F 预检无解。
- 至少一个篡改检测测试。
- Excel 往返。
- API 四类视图与导出。
- 前端构建通过。

如果修改算法/数据，重新生成 `TEST_REPORT` 中的数字。

## 11. DSH 插件

插件已实现（0.2.0）；修改时遵守：

- 内核仍在 `engine/aiwish`，`dsh-plugin` 只做宿主/客户端/打包适配，不复制算法。
- DSH 0.2.2-rc.1 的安装格式是 `.tgz`，**不支持 ZIP 直装**；不要为了“ZIP”字样改后缀或虚报。
- 宿主插件启动内置 Python sidecar，只绑定 127.0.0.1；浏览器经同源 `/plugins/aiwish/*` 代理访问。
- 侧边栏是 DOM 注入，不是稳定 slot API；修改客户端后必须在真实 DSH 中回归。
- `dsh.bundle.platforms` 必须与运行时一致（darwin 包不能伪装成 win32）。
- Windows 包未实机验证；不要把结构检查写成运行通过。
- 自然语言规则变更必须结构化 patch → 校验 → 用户确认 → 应用。
- 个人信息默认本地，不直接发大模型。
- 升级 DSH 后重新执行 `PLUGIN_TECH_VALIDATION.md` 的验证项。

## 12. 提交前检查

```bash
PYTHONPATH=engine:backend .venv/bin/pytest
cd frontend && pnpm run build
```

检查 `git diff` 不包含：

- 生成的 DB / XLSX；
- 大量日志；
- 临时截图；
- 硬编码的课表结果；
- 被临时关闭的硬约束。

## 13. 语言与风格

- 用户界面中文；代码标识符英文。
- Python 使用类型标注、dataclass、明确错误码。
- 不要用 `except Exception: pass` 掩盖求解/校验错误。
- 错误信息要能指导用户：资源不足、容量不足、时段不足、数据非法。
- 注释解释“为什么”，不要复述代码。
