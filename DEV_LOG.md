# DEV LOG · 开发过程与关键技术决策

> 记录真实开发过程，包括走过的弯路。所有时间为 2026-11-25（Asia/Shanghai）。

## 00. 起点

输入是一份完整的新高考走班排课需求：学生选科 24 组合、62 名教师、31 个教学时段、13 条硬约束、7 条软约束、7 个测试场景、工作台、Excel、独立校验与交付文档。

约束：本地、无 GPU、无付费 API、真实求解器、不得用预设课表冒充算法结果。

第一原则：**先让核心算法真实可解、可验证，再谈界面**。

## 01. 环境：conda Python 的 SSL 坏了

初始 `python3` 指向 miniconda 3.13，安装依赖时报：

```text
Can't connect to HTTPS URL because the SSL module is not available
ImportError: dlopen(.../_ssl.cpython-313-darwin.so, ... libssl.3.dylib ...)
```

尝试在 conda venv 中安装同样失败：venv 继承了损坏的 SSL。

**决策**：改用 `/opt/homebrew/bin/python3`（3.13.1，OpenSSL 3.6.4），创建项目 `.venv`。`start.sh` 后续加入自动寻找可用 Python 的逻辑，避免用户踩同一个坑。

## 02. 架构：核心引擎与 Web 适配层分离

目录决策：

```text
engine/aiwish/     纯 Python，可 CLI 独立运行
backend/app/       FastAPI + SQLite + Excel
frontend/          React + TypeScript
```

原因：

1. 未来可能做 DSH 插件，核心不能绑死 FastAPI；
2. 校验器必须独立于求解器；
3. 测试可以只跑核心，不启动服务器；
4. API/CLI/未来工具面共享同一套能力。

`engine/aiwish/tools.py` 是未来 DSH 工具适配的稳定面，不是 DSH 插件本体。

## 03. 数据模型：先固定“可解释的教学班”

需求最复杂的不是选科，而是“走班”的语义。

最终采用四层数据：

1. `Student`：行政班、外语、首选、再选。
2. `TeachingClass`：固定学生集合、固定教师、固定教室、若干周任务。
3. `LessonTask`：一节课（1 个时段），带 allowed_slots、学生集合、教师、教室。
4. `Scenario`：时间模型、课程配置、规则、资源。

**关键决定**：教学班和资源分配在求解前完成；CP-SAT 只决定**每个任务放在哪个时段**。这样，教学班是显式可审计的，求解器不会“发明”一个班级，也不会从结果反推班级。

## 04. 时间模型：42 格、31 active、五阶段

最初把 7×6 误算成 36 格，后来修正为 **42 个网格格**。其中 active 31：

- 基础段 13（语文 5 + 数学 8）
- 外语段 6
- 首选段 4
- 再选 A 4
- 再选 B 4

这个分块有三个好处：

1. 每名学生的 31 个课时正好映射到 31 个 active 时段；
2. 物理/历史只在首选段，外语只在外语段，结构上满足 H-11/H-14；
3. CP-SAT 搜索空间大幅缩小。

代价是刚性：跨类别时间不能自由交换。已在 ASSUMPTIONS A-03 记录。

## 05. 再选科目：用“有序配对”解决四科禁止

四选二有 6 种组合。若同一走班组同时开四科，学生会同时被排进两门课，不可行；若只开两科，又覆盖不了选另外两科的学生。

最终方案：固定科目顺序：

```text
生物 → 化学 → 地理 → 政治
```

每名学生的两门再选，较早者进 A 段，较晚者进 B 段。

- A 段最多 3 科：生物/化学/地理
- B 段最多 3 科：化学/地理/政治
- 永远不可能 4 科

这是“复杂情况下允许三科”的直接实现。代价是 D/F 会出现三科并行，且两科优先只能作为软目标。已在 ASSUMPTIONS A-05 记录。

## 06. CP-SAT 模型

每个任务一个 0/1 变量集合 `x[task, slot]`，以及一个整数 `assigned[task]`：

- 每个任务恰好一个时段；
- 学生每时段恰好 1 节课（31 任务 / 31 时段）；
- 教师每时段 ≤1；
- 教室每时段 ≤1；
- 同一教学班每天同科 ≤2；
- 数学 8 个任务严格按顺序：`t0 < t1 < ... < t7`；
- 教师不可排时间在变量生成阶段过滤；
- 目标函数：先正课后落实 + 教师空堂（仅对 ≥3 任务的教师）。

**没有**把“学生冲突”“教室冲突”等交给后处理，全部在模型里。

### 6.1 第一次失败：提示重复

提示（hint）先对选中变量 `AddHint(1)`，再在补全循环中又对同一变量 `AddHint(1)`：

```text
Invalid model: The solution hint contains duplicate variables like the variable with index #0
```

修复：每个变量只 hint 一次，非选中值补 0。

### 6.2 第二次失败：F 在 presolve 阶段 INFEASIBLE

模型报空 `bool_or`。排查发现：某行政班的语文教师和数学教师在同一 base 时段都不可排。31 个任务需要填满 31 个时段，学生在那个时段没有任何合法任务。

这不是求解器 bug，而是模拟数据与 31/31 零松弛模型冲突。

修复：

1. 数据生成阶段协调，避免同一行政班两个基础科教师同一时段都不可用；
2. 最终只给数学教师生成不可排时间，保证每班至少一门基础课可用；
3. 在 ASSUMPTIONS 明确记录该模型限制。

这里没有把“学生每时段恰好 1 节”改成 `<=1` 来伪造可行——那会掩盖课时缺失。

### 6.3 E 场景：日语教师不足

E 场景 48 名日语学生按 45 人目标拆成 2 个班，但只有 1 名日语教师满足全 6 节可用。两个班同一时段上课 → 教师冲突。

修复：

- 外语目标班额改为 54（硬上限 60），48 人合一班；
- `_pick_teacher` 在需要并行的段禁止复用教师；候选不足直接报 `teacher_capacity`，不再“悄悄复用”。

## 07. 独立校验器

`validator.py` 不导入 `solver.py` / `builder.py`，从场景 + 教学班元数据 + 任务列表重新推导：

- 学生、教师、教室冲突；
- 逐生逐科逐细分课程课时；
- 容量；
- 教师不可排；
- 每日上限；
- 数学序列；
- 首选/外语/再选走班规则；
- 四类视图一致性。

测试故意篡改课表：同班两任务同格、移除学生成员、塞入 100 人，校验器均能检出。

## 08. 无解与严格规则

场景 G 只有 1 名物理教师，物理 162 人。预检直接证明 1 个班装不下（60 人上限），返回 `PRECHECK_INFEASIBLE`，不进入求解。

另外，需求 H-12 原文“物理历史走班组最多两个行政班，暂按…待确认”。在 F 中启用 cap=2 后，物理需要 4 个班，3 名教师无法同时开课，预检返回：

```text
物理按走班组不超过2个行政班拆分后需要4个教学班，但只有3名教师且同一时段必须同时授课
```

**决策**：默认不启用（0），但校验器输出警告，规则页可一键启用，启用后如实无解。不把“未启用”伪装成“已满足”。

## 09. 工作台

先做 API，再做 React。页面结构按教务人员任务组织，而不是按技术模块：

- 工作台：总览 / 自动排课 / 校验
- 基础数据：学生 / 教师 / 课程 / 教室 / 时间模型
- 走班与规则：教学班 / 规则
- 课表：行政班 / 学生 / 教师 / 教室
- 数据交换：Excel

UI 采用深蓝侧栏 + 浅底卡片，中文文案，强调状态、证据和走班关系。

行政班课表设计为“走班时段同格多教学班”，因为行政班视角下同一时段确实可能有物理/历史等多个班。

## 10. 数据库与 API

SQLite 采用 JSON 快照：

- `scenarios(id, payload, updated_at)`
- `runs(id, scenario_id, status, solver_status, created_at, scenario_updated_at, payload)`

原因：V0.1 字段还会变，JSON 快照比频繁迁移更稳；也方便保留完整求解结果与历史。

API 层完全调用 `run_scenario`，不自己算课表。

求解同步执行：F 约 0.2s，用户体验可接受；超时上限 30s。若未来 1000+ 人，需要改成后台任务 + 进度轮询。

## 11. Excel

导出 11 个工作表：学生、教师、课程、教室、教学班、行政班课表、三类长表、校验结果、总览。

导入器做了两件事：

1. 兼容模板（表头在第 1 行）和导出文件（表头在第 3 行）；
2. 严格校验后再写库，错误行不落库。

导出→导入往返测试通过。

## 12. 前端调试

- TypeScript 首次构建失败：`onClick={solve}` 把可选参数函数直接当 MouseEvent handler；改为 `() => solve()`。
- 时间模型页漏 import `MetricCard`；补齐。
- 42/36 网格误写；全局修正。
- UI 巡检 15 个页面，无 console error。

## 12.1 教师绑定补充

需求要求“指定任课教师 / 候选范围 / 不可排时间”，最初只做了候选池与不可排时间。

补齐：

- `Scenario.teacher_bindings` 数据字段；
- 基础科绑定键：`语文|高一(1)班`、`数学|高一(1)班`；
- 教师资源页的 8 行绑定表；
- `PATCH /teacher-bindings` 校验教师候选科目与行政班存在；
- Builder 优先使用绑定教师；绑定教师不可用或同段重复绑定时直接报错，不自动换人；
- 外语/走班绑定键在数据层预留，等业务规则确认。

浏览器端到端验证：绑定 T-CN-03 后重新求解，语文教学班教师变为 T-CN-03，独立校验通过。

## 13. 测试

最终：

```text
40 passed in ~11s
```

覆盖核心、校验器篡改、Excel、API、工具面。

## 14. 还没做的

- 具体教学班“指定教师”绑定；
- 局部调课/重新求解；
- DSH 插件；
- 1000+ 人压力测试；
- 真实学校数据兼容。

这些都写入 HANDOFF，不假装完成。

## 15. 给视频/演示的素材点

1. 打开 F 场景，320 人、24 组合。
2. 一键排课，0.2s 内 OPTIMAL。
3. 校验页 11 项全 0。
4. 行政班课表展示同一格物理/历史/再选多教学班。
5. 教学班页看跨班合班、教师、教室、学生名单。
6. 规则页启用“最多两个行政班”，重跑，看到真实无解证明。
7. 场景 G 打开，看到资源不足预检无解。
8. Excel 导出，查看学生/教师/教室课表与校验结果。

---

# 2026-11-26 · 产品形态调整：DSH 插件优先

## 16. 为什么改

需求方要求优先以 DSH 插件交付，降低分发/部署/运维成本：用户安装 DSH，导入插件包即可使用，不装 Python、不配服务器。

先做协议验证，不假设宿主支持。

## 17. 检查 DSH 0.2.2-rc.1

- CLI：`/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh`。
- 插件管理器：`@deepseek-ai/dsh-plugin-manager`，安装规格是 npm 包名/本地目录/Git/tarball，**没有 ZIP**。
- 宿主 Web：`@deepseek-ai/dsh-host-webserver`，支持 `register({kind:'prefix'})`。
- 客户端模块：`dsh.client` + `window.__ModuleLoader__.load`。
- 会议插件 `dsh-meeting-notes@0.6.4` 已用 DOM 注入侧边栏 + iframe + 原生子进程；没有稳定 sidebar slot API。

结论：可以做，但交付物必须是 `.tgz`；ZIP 只能作为分发外壳。

## 18. 插件架构

```text
DSH 宿主
  └─ dsh-aiwish-timetable (host half)
       ├─ spawn runtime/bin/python3 -m app.plugin_server
       ├─ 代理 /plugins/aiwish/* → 127.0.0.1:<random port>
       └─ 浏览器 iframe
            └─ app/index.html (React HashRouter)
                 └─ /plugins/aiwish/api/* → 同一 FastAPI
```

- 不改排课算法；`server/engine` 是构建时复制的 `engine/aiwish`。
- sidecar 只绑 127.0.0.1，端口由 OS 分配，stdout 打印 `AIWISH_PORT=...`。
- 宿主代理同源，页面不暴露 sidecar 端口。

## 19. 冒烟验证

先写了一个 3.6KB 的 smoke 插件，安装到隔离 `DSH_HOME` 的 web profile：

- 侧边栏出现「排课」；
- iframe 打开；
- `/plugins/aiwish/api/health` 200；
- 说明协议路线可行。

然后才做正式插件。

## 20. 前端适配

- `BrowserRouter` → `HashRouter`，iframe/独立页面都不需要 SPA 回退。
- Vite `base: './'`，同一份 dist 可部署在 `/` 或 `/plugins/aiwish/app/`。
- API 基址自动识别 `/plugins/aiwish/` → `/plugins/aiwish`。
- FastAPI 增加 `AIWISH_STATIC_DIR`/`AIWISH_STATIC_PREFIX`，sidecar 模式把静态资源挂到 `/app`。
- 独立 `start.sh` 和 DSH 插件共用同一套 API。

## 21. Python 运行时

### macOS

- python-build-standalone 3.12.16（aarch64）。
- cp312 wheels：OR-Tools 9.15.6755、FastAPI、uvicorn、openpyxl、pydantic 等。
- 清理 test/idlelib/tkinter/pip，运行时 194MB，tgz 82MB。
- 实测 CP-SAT 在插件内置 Python 中 OPTIMAL。
- 发现 `ortools.sat.python.cp_model` import 时依赖 numpy 和 pandas，不能裁掉。

### Windows

- Python 3.12.10 embeddable + cp312 win_amd64 wheels。
- 解压到 `Lib/site-packages`，写 `python312._pth`。
- 结构检查：PE32+、`_ssl.pyd`、`libssl-3.dll`、`ortools/.libs/*.dll`、85 个 `.pyd`。
- 当前机器没有 Windows/VM，无法执行；不标记为已验证。

## 22. 包格式

DSH 只接受 `.tgz`。最终交付：

- `dist/dsh-aiwish-timetable-darwin/dsh-aiwish-timetable-0.2.0.tgz`
- `dist/dsh-aiwish-timetable-win32/dsh-aiwish-timetable-0.2.0.tgz`
- 两个 ZIP 分发包装（内含 tgz + 安装说明 + SHA256）

ZIP 不能直接喂给 DSH；文档已明确。

## 23. 端到端验证

隔离 `DSH_HOME=/tmp/dsh-aiwish-bundle`：

- 安装 tgz 1.8s；
- DSH 启动后侧边栏「智能排课」；
- iframe H1 正常，无 console error；
- 场景 F 加载；
- 一键排课 → OPTIMAL，独立校验通过；
- 导出 368KB xlsx；multipart 导入 200；重排 OPTIMAL；
- 卸载后重启，`/plugins/aiwish/*` 404。

DSH 新 profile 的登录/API Key 引导会拦截 iframe 鼠标事件；这是宿主账户引导，不是插件；测试时移除遮罩后用 JS 触发按钮。

## 24. 失败/修正

- 初次插件数据目录固定 `~/.dsh`，在隔离 DSH_HOME 下被沙箱拒绝（EPERM）。改为优先 `$DSH_HOME`。
- Windows 包最初包名 `-win32`，但客户端模块 id 固定为 `dsh-aiwish-timetable`，会导致模块注册不匹配。改回同一包名，仅 `dsh.bundle.platforms` 不同。
- DSH 只支持 tgz，不能为了满足“ZIP”字样把 tgz 改后缀冒充当 ZIP；最终明确协议限制。
- 侧边栏 DOM 注入在 DSH 0.2.2-rc.1 验证，但不是稳定 API；记录为风险。

## 25. 尚未验证

- Windows 实机。
- macOS Intel。
- DSH 0.3+。
- 1000+ 学生。

---

# 2026-11-26 · V0.1 工作台 UX 优化

## 26. 真实老师视角

原有工作台偏“系统管理员视角”：数据、规则、算法参数都在，但第一次打开不知道先做什么。按教务老师的工作顺序重新组织：

```text
准备数据 → 设置规则 → 自动排课 → 查看结果 → 导出课表
```

不修改核心算法，只改组织方式和入口。

## 27. 首页排课准备

新增 `PreparationPanel`：

- 6 项：学生与选科、教师与任课、教室资源、课程与课时、上课时间、排课规则；
- 每项显示数量、缺失信息和直达链接；
- 6/6 进度环；
- 「排课前检查」调用 `/preflight`，不直接求解；
- 只有预检通过才从首页自动排课；否则留在面板展示原因。

预检使用普通语言区分：

- “还没有学生数据”
- “缺少 化学、历史 教师”
- “教师或教室资源不足，暂时无法排课”
- “配置完整，可以自动排课”

## 28. 首次使用

`FirstRunDialog` 两个选择：

- 使用示例数据体验 → 加载 F；
- 创建自己的排课方案 → `POST /api/scenarios/custom` 生成空白方案。

示例数据通过 `is_sample` 标记，顶部 Badge、首页提示条、场景下拉后缀三处提示，避免误认为学校数据。

## 29. 分项导入

新增：

- `GET /api/excel/template?sid=&sheet=students|teachers|rooms|courses`
- `POST /api/scenarios/{sid}/import?mode=&sheet=...`

`import_workbook(only_sheet=...)` 只处理指定类别；空模板导入被拒绝，避免清空已有数据；全局 workbook 校验只在整套导入时执行，允许先导入学生、再导入教师/教室。

导入反馈增加：

- `failed_rows`
- `duplicates`
- `warnings`
- `errors`

前端 `ImportActions` 在学生、教师、教室、课程页面顶部复用；手动新增 API + Modal。

## 30. 导航与高级设置

侧栏改为：

- 开始：排课总览、排课准备
- 数据准备：学生、教师、课程、教室、时间
- 规则与排课：规则、自动排课
- 课表与结果：四类课表、教学班、校验
- 数据与备份：Excel

自动排课页把时间上限、worker、软约束权重收进 `<details>` 高级设置。

## 31. UX 回归

Playwright 真实浏览器走通：

- 路径 A：首次打开 → 示例 F → 预检 → OPTIMAL → 行政班课表 → Excel；
- 路径 B：创建空白方案 → 分项导入学生320/教师62/教室26 → 预检 → OPTIMAL。

手动新增学生/教师/教室均验证通过。

后端测试从 40 增至 45。
