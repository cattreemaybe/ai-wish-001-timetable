# TEST REPORT · 真实测试结果

测试日期：2026-11-25（Asia/Shanghai）
项目版本：V0.1.0

## 1. 环境

| 项 | 值 |
|---|---|
| 机器 | macOS (arm64) |
| Python | 3.13.1（Homebrew，OpenSSL 3.6.4） |
| OR-Tools | 9.15.6755 |
| FastAPI | 0.165.0 |
| SQLite | Python 标准库 |
| Node.js | 24.21.0 |
| pnpm | 10.28.2 |
| React / Vite | React 18.3 / Vite 6.4 |
| 浏览器验证 | Chrome Headless（Playwright） |

> 本机 conda 的 Python 3.13 缺少 `libssl.3.dylib`，无法安装依赖。项目改用 Homebrew Python；`start.sh` 也包含“寻找可用 Python”的逻辑。详见 DEV_LOG。

## 2. 自动化测试

命令：

```bash
PYTHONPATH=engine:backend .venv/bin/pytest
```

结果：

```text
40 passed, 1 warning in ~11s
```

覆盖：

| 测试文件 | 覆盖内容 |
|---|---|
| `test_data.py` | 固定种子、24 组合、31 课时、A/B 组合差异、建班任务数、D 场景每段≤3科、E 外语分班 |
| `test_solver.py` | A-F 全部求解 + 独立校验；F 指标；A 无走班；G 预检无解；严格 cap=2 无解；数学交替；教师绑定 |
| `test_validator.py` | 正常通过；篡改后检测学生/教室冲突、课时缺失、超容量 |
| `test_excel.py` | 导出含四类课表和校验；模板表头；导出→导入往返；非法组合拒绝 |
| `test_api.py` | 健康检查、场景、求解、四类视图、Excel、编辑校验、严格 cap、时间模型、重新校验、教师绑定 API |
| `test_tools.py` | 未来 DSH 工具面、规则确认流程、分析、导出、局部调课未支持声明 |

前端构建：

```text
✓ 1598 modules transformed
dist/assets/index-*.js  268.28 kB │ gzip: 81.50 kB
```

浏览器巡检：15 个页面全部加载，无 console error / pageerror；教师不可排时间弹窗、学生编辑弹窗、课表、校验页均正常。

## 3. 场景结果（真实运行）

复现：

```bash
PYTHONPATH=engine .venv/bin/python scripts/run_all_scenarios.py
```

| 场景 | 状态 | 求解耗时 | 教学班 | 周任务 | 走班学生 | 合班 | 独立校验 |
|---|---|---:|---:|---:|---:|---:|---|
| A | OPTIMAL | 0.026s | 6 | 31 | 0 | 0 | 通过 |
| B | OPTIMAL | 0.028s | 9 | 43 | 40 | 0 | 通过 |
| C | OPTIMAL | 0.045s | 12 | 62 | 80 | 2 | 通过 |
| D | OPTIMAL | 0.048s | 14 | 70 | 80 | 8 | 通过 |
| E | OPTIMAL | 0.045s | 12 | 62 | 80 | 8 | 通过 |
| F | OPTIMAL | 0.161s | 41 | 218 | 320 | 25 | 通过 |
| G | PRECHECK_INFEASIBLE | — | 0 | 0 | — | — | 无课表，未放宽约束 |

> 周任务数不是学生课时数。B/C/D/E 中一个行政班会同时上多个教学班，因此教学任务数大于 31。

## 4. 综合场景 F 详情

| 指标 | 值 |
|---|---:|
| 行政班 | 8 |
| 学生 | 320 |
| 选科组合（含外语） | 24 |
| 教师 | 62 |
| 教室 | 26 |
| CP-SAT 状态 | OPTIMAL |
| 求解耗时 | 0.161s（一次运行） |
| 教学班 | 41 |
| 其中基础班 | 16 |
| 其中外语班 | 7 |
| 其中走班班 | 18 |
| 周任务 | 218 |
| 学生-课时记录 | 9,920 |
| 走班学生 | 320（100%） |
| 走班总人次 | 640 |
| 合班教学班 | 25 |
| 走班合班 | 18 |
| 教师空堂 | 0 |
| 平均班额 | 46.8 |
| 最大班额 | 54 |
| 已排时段 | 31 / 31 |
| 硬约束违规 | 0 |

### 独立校验明细

| 检查项 | 违规数 |
|---|---:|
| 学生时间冲突 | 0 |
| 教师时间冲突 | 0 |
| 教室时间冲突 | 0 |
| 学生课时缺失 | 0 |
| 教室超容量 | 0 |
| 教师不可排时间 | 0 |
| 每日同科上限 | 0 |
| 数学交替 | 0 |
| 走班规则 | 0 |
| 四视图一致性 | 0 |
| 非法时段 | 0 |

视图条目一致性：

- 学生视图条目 = 9,920
- 教师视图条目 = 218
- 教室视图条目 = 218
- 行政班视图条目 = 512

## 5. 无解场景 G：证明而不是超时

场景 G 将物理教师数量降为 1。物理 162 名学生，最大教室 60 人：

```text
数据预检证明无解：162 名学生最多只能拆成 1 个教学班，按最大教室 60 人仍超出容量
```

- `status = infeasible`
- `solver_status = PRECHECK_INFEASIBLE`
- 没有调用求解器生成课表
- 没有放宽容量
- 没有把结果写成 `UNKNOWN` 或“成功”

## 6. 严格“两个行政班”规则测试

在 F 场景设置 `walk_group_admin_class_cap=2`：

```text
数据预检证明无解：物理按走班组不超过2个行政班拆分后需要4个教学班，
但只有3名教师且同一时段必须同时授课
```

这是本项目最重要的需求冲突证据之一：

- 需求 H-12 标注“暂定”，但按原文严格建模会与 3 名物理教师冲突。
- V0.1 默认不启用，并在校验报告中输出警告，不冒充已满足。
- 用户可在规则页一键启用，系统会如实报无解。

## 7. 校验器篡改测试

为避免“校验器只是复述求解器结果”，测试故意篡改一个已验证课表：

| 篡改 | 期望 | 结果 |
|---|---|---|
| 把同班两个任务放到同一时段 | 学生/教室冲突 >0 | 检出 |
| 从任务中移除一名学生的成员关系 | 课时缺失 >0 | 检出 |
| 给任务塞入 100 名虚构学生 | 教室超容量 >0 | 检出 |

## 8. Excel 测试

- 导出包含 11 个工作表：总览、学生选科、教师资源、课程配置、教室资源、教学班、行政班课表、学生课表、教师课表、教室课表、校验结果。
- 导出文件约 360KB（F 场景，含 9,920 条学生课表记录）。
- 导出→导入 replace 往返：学生 320、教师 62、教室 26、课程配置 22 行，全部通过。
- 模板表头正确。
- 非法再选组合（生物+生物）被拒绝，原场景不被修改。

## 9. API 测试

- `GET /api/health` OK。
- 7 个场景加载。
- `POST /api/scenarios/F/solve` 返回 OPTIMAL，validation.passed=true。
- 四类视图均可取到 42 个网格格；学生视图 31 个任务。
- `POST /api/runs/{id}/validate` 可重复校验（upsert 修复后）。
- 时间模型原样 PUT 通过；少于 42 格返回 422。
- 严格 cap=2 通过 API 返回 INFEASIBLE 且无任务；reset 后重新求解成功。
- 非法学生组合、非法教师时段返回 422。

## 10. 前端验证

教师绑定已通过浏览器端到端验证：选择“高一(1)班语文 = T-CN-03”，保存，重新求解，返回的语文教学班教师为 T-CN-03，独立校验仍通过。

- 15 个页面无 console error。
- 总览页展示 F 的 41 个教学班、0 违规、640 走班人次。
- 行政班课表正确显示走班时段同格多教学班。
- 校验页显示 0 硬约束违规与“走班组 cap 未启用”的警告。
- 教师弹窗显示 42 个时段按钮，可切换不可排。
- 截图见 `docs/screenshots/`。

## 11. 失败与回归记录

### 11.1 第一次 CP-SAT 运行：MODEL_INVALID

初始提示（hint）实现里，同一个布尔变量被 `AddHint(..., 1)` 两次：

```text
Invalid model: The solution hint contains duplicate variables like the variable with index #0
```

**修复**：每个变量只 hint 一次，其余允许值为 0。回归测试要求所有场景可解。

### 11.2 第一次 F 求解：空 bool_or 导致 INFEASIBLE

由于模拟数据同时给某行政班的语文和数学教师设置了同一时段不可排，而 31 节任务要填满 31 个时段，学生在那个时段无任何合法任务。CP-SAT 在 presolve 阶段直接给出空 `bool_or`。

**修复**：

1. 数据生成阶段避免同一行政班语文/数学教师在同一 base 时段同时不可排；
2. 最终模拟数据只给数学教师生成不可排时间，保证每班至少有一门基础课可用；
3. 在 ASSUMPTIONS 中明确这是 31/31 零松弛模型的限制，而不是“把约束悄悄删掉”。

### 11.3 E 场景：日语两个班共用一名教师

E 场景日语 48 人，按 45 人目标拆成 2 个班；但第 2 名日语教师在前两个外语时段不可排，只有 1 名教师满足“全 6 节可用”，两个班同时上课冲突。

**修复**：

- 外语班目标班额改为 54（硬上限 60），48 人合成 1 个班；
- `_pick_teacher` 在需要同时开班的场景中禁止复用教师，候选不足直接报 `teacher_capacity`，不再静默复用。

### 11.4 网格数误写为 36

初版文档/校验把 7×6 误写成 36。实际应为 **42 个网格格、31 个 active 时段**。已修正 API、测试、前端文案。

## 12. 尚缺的测试

- 1000+ 学生、20+ 行政班压力测试。
- 多周轮换/临时调课。
- 真实学校数据导入的字段兼容性。
- 浏览器移动端真机测试。
- Windows DSH 插件实机运行（当前只完成结构构建与平台守卫测试）。
- DSH 0.3+ 客户端 slot 协议回归。

这些缺口已在 HANDOFF 中列为下一阶段任务，不能用现有结果冒充完成。

## 13. DSH 插件端到端验证（2026-11-26）

DSH CLI / Desktop：0.2.2-rc.1，macOS Apple Silicon。

| 步骤 | 结果 |
|---|---|
| 全新 `DSH_HOME` + web profile | 初始化成功 |
| 安装 `dsh-aiwish-timetable-0.2.0.tgz`（82MB） | 成功，pnpm 约 1.8s |
| 启动 DSH web | 侧边栏出现「智能排课」 |
| iframe 加载 | H1「新高考智能走班排课工作台」，无 console error |
| 内置 Python | `diag.python` 指向插件 `runtime/bin/python3`，非系统 Python |
| 场景加载 | F 场景 320 人、24 组合 |
| 一键排课 | `OPTIMAL`，独立校验通过 |
| 校验页 | 11 项全 0，218 任务 / 320 学生 / 62 教师 / 26 教室 |
| Excel 导出 | 200，368,333 bytes，11 个工作表 |
| Excel 导入 | multipart 上传 200，students=320 |
| 导入后重排 | `OPTIMAL`，validation=true，218 tasks |
| 卸载 | profile 依赖与 bundle 选择移除；重启后 `/plugins/aiwish/*` = 404 |

Windows x64 包：

- 已构建 tgz（约 59MB），`dsh.bundle.platforms=["win32"]`。
- 在 macOS 安装时被 DSH 正确拒绝：`Bundle supports Host platforms win32; the DSH Host is running darwin`。
- Python/OR-Tools/numpy/pandas DLL 与 `.pyd` 结构检查通过。
- **未在 Windows 实机运行**；验收清单见 `PLUGIN_WINDOWS_ACCEPTANCE.md`。

限制：

- DSH 插件管理器仅接受 tgz/目录/npm/Git，不接受 ZIP 直装；ZIP 是分发包装。
- 插件侧边栏是 DOM 注入，不是稳定官方 slot API。
- macOS 仅 arm64；Windows 未实机验证。

详见 `PLUGIN_TECH_VALIDATION.md`。

## 14. 更新后的测试结论

- 核心 40 个 pytest 全通过。
- 前端生产构建通过（hash router + plugin base）。
- macOS DSH 插件安装、启动、排课、校验、Excel、卸载通过。
- Windows 插件包结构完成，但运行验证仍为待办，不能标记为“已支持”。
