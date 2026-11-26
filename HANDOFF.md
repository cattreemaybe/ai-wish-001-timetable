# HANDOFF · 项目现状、已知问题与下一阶段

## 1. 一句话状态

V0.1 已完成：独立 CP-SAT 引擎、独立校验器、FastAPI + SQLite、React 工作台、Excel、A-G 场景、40 个测试和交付文档。综合场景 F（8 班 320 人）真实求解为 OPTIMAL，独立校验 0 违规。

**2026-11-26 产品形态更新**：已交付 DSH 插件 0.2.0。macOS arm64 包在隔离 DSH 0.2.2-rc.1 中完成安装、启动、排课、校验、Excel 导入导出、卸载全流程；Windows x64 包已构建并通过平台守卫/结构检查，但无 Windows 实机运行验证。DSH 只接受 `.tgz`，ZIP 仅为分发包装。

## 2. 立即接手

### DSH 插件（优先交付）

```bash
# macOS arm64
dsh plugin --profile desktop add /absolute/path/dist/dsh-aiwish-timetable-darwin/dsh-aiwish-timetable-0.2.0.tgz
# Windows x64
dsh plugin --profile desktop add C:\absolute\path\dist\dsh-aiwish-timetable-win32\dsh-aiwish-timetable-0.2.0.tgz
```

刷新 DSH → 侧边栏「智能排课」。

### 独立源码

```bash
cd AI-WISH-001
./start.sh
# http://127.0.0.1:8000
```

开发：

```bash
./dev.sh
```

测试：

```bash
./test.sh
```

核心 CLI：

```bash
PYTHONPATH=engine .venv/bin/python -m aiwish.cli run F --summary
```

## 3. 已实现

### 核心

- 24 种外语×选科组合模拟数据，固定种子。
- 31 active 时段 / 42 网格。
- 语文、数学、英语、日语、物理、历史、生物、化学、地理、政治课程配置。
- 分阶段建班：基础段、外语段、首选段、再选 A/B 段。
- 教师候选池、不可排时间、周课时上限、基础科行政班绑定。
- 教室容量与时间冲突。
- CP-SAT 时间求解，区分 OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN/MODEL_INVALID/PRECHECK_INFEASIBLE。
- 独立校验器，11 项核心指标全 0 才通过。
- 指标：求解耗时、教学班、合班、走班学生、走班人次、教师空堂等。
- 严格 cap=2 与 G 场景的无解证明。

### Web

- 总览、自动排课、校验、学生、教师、课程、教室、时间模型、教学班、规则、四类课表、Excel。
- 本地 SQLite 保存场景快照与运行历史。
- 学生选科编辑、教师不可排时间 42 格编辑、基础科教师绑定、课程课时编辑、教室容量编辑。
- 规则页可启停待确认的走班组 cap、调整软约束权重。
- Excel 模板、导入、导出（含四类课表与校验报告）。

### DSH 插件

- 宿主插件：`dsh-plugin/src/lib/index.js`，启动内置 Python sidecar 并代理 `/plugins/aiwish/*`。
- 客户端入口：`dsh-plugin/src/lib/client.js`，侧边栏「智能排课」+ 同源 iframe。
- 包产物：`dist/dsh-aiwish-timetable-darwin/*.tgz`、`dist/dsh-aiwish-timetable-win32/*.tgz`。
- 分发 ZIP：`dist/AI-WISH-001-DSH-darwin-arm64.zip`、`dist/AI-WISH-001-DSH-win32-x64.zip`。
- 详细验证：`PLUGIN_TECH_VALIDATION.md`。

### 文档

README / REQUIREMENTS / ASSUMPTIONS / TEST_REPORT / DEV_LOG / HANDOFF / AGENTS / PLUGIN_TECH_VALIDATION / PLUGIN_WINDOWS_ACCEPTANCE / DSH 计划。

## 4. 关键文件

| 文件 | 作用 |
|---|---|
| `engine/aiwish/builder.py` | 建班与资源预分配 |
| `engine/aiwish/solver.py` | CP-SAT 时间求解 |
| `engine/aiwish/validator.py` | 独立校验 |
| `engine/aiwish/runner.py` | 端到端入口 |
| `engine/aiwish/tools.py` | DSH 对话工具面（保留） |
| `backend/app/main.py` | FastAPI |
| `backend/app/db.py` | SQLite 快照 |
| `backend/app/excel_io.py` | Excel |
| `frontend/src/pages/TimetablePage.tsx` | 四类课表 |
| `frontend/src/pages/Rules.tsx` | 规则配置 |

## 5. 已确认的事实（可复现）

- F：320 学生、8 班、24 组合、41 教学班、218 任务、0 硬约束违规、OPTIMAL、约 0.16s。
- G：物理教师 1 人，预检无解，不生成课表。
- cap=2：F 需要 4 个物理班但只有 3 名教师，预检无解。
- 40 tests passed。
- Excel 导出约 360KB，导出→导入往返成功。
- 浏览器 15 页无 console error。

## 6. 已知问题 / 风险

### P0：需求冲突需要拍板

“物理/历史走班组最多两个行政班”与 3 名物理教师资源冲突。需求方需要选择：

- 增加物理教师；
- 放宽走班组 cap；
- 调整首选段长度/学生空堂；
- 调整班级规模或选科分布。

当前默认关闭并在校验报告警告，规则页可一键启用复现无解。

### P1：31/31 零松弛

每生 31 节 / 31 时段，没有空堂。教师不可排时间、走班组合没有缓冲。真实学校通常有自习/机动时段；需要需求方确认是否增加时段或允许空堂。

### P1：走班/外语教师绑定未完成

基础科（语文/数学）已支持按行政班绑定具体教师（UI + API），数据层也为外语/走班预留了绑定键。但外语/走班教学班的指定教师 UI、候选范围业务规则仍需确认。

### P1：局部调课未实现

`reschedule_partial` 只返回未支持声明。需要设计：

- 锁定已排任务；
- 只释放冲突窗口；
- 增量 CP-SAT；
- 与当前完整重排对比。

### P2：规则目标覆盖不完整

进入 CP-SAT 目标的只有“先正课后落实”和“教师空堂”。走班次数、合班、教学班数量主要由建班阶段决定，当前作为指标输出，不是联合优化。

### P1：DSH 插件协议限制

- DSH 0.2.2-rc.1 不支持 ZIP 直装，只接受 tgz/目录/npm/Git；ZIP 仅为分发包装。
- 侧边栏入口是 DOM 注入，不是稳定官方 slot API，DSH 升级需回归。
- Windows x64 未实机运行；必须按 `PLUGIN_WINDOWS_ACCEPTANCE.md` 验收。
- 插件包 tgz 约 59-82MB，首次打开需数秒启动 sidecar。

### P2：同步求解

API 在请求内同步求解。F 约 0.2s 没问题；1000+ 人时需要后台任务、进度、取消。

### P2：数据层 JSON 快照

V0.1 便于迭代，但不适合长期多用户/审计。生产化需要规范表结构、版本迁移、权限。

### P3：前端

未做移动端深度适配；未做拖拽调课；未做虚拟滚动（320 行分页已够用）。

## 7. 下一阶段建议

### 阶段 1：需求确认（最重要）

与需求提出者逐条确认：

1. 走班组 cap=2 是否保留？物理教师是否可增加？
2. 是否允许学生空堂/增加机动时段？
3. 数学交替是否必须从正课开始？
4. 教师绑定规则：行政班绑定？教学班绑定？候选范围？
5. 再选科目是否固定顺序？是否允许动态走班组？
6. 真实教室容量、班级规模、作息。

### 阶段 2：算法增强

- 支持教师-教学班预先绑定。
- 引入“走班组”显式对象，支持 2/3 科组合配置。
- 支持空堂/机动时段，放宽 31/31。
- 局部调课：锁定窗口 + 增量求解。
- 多目标 Pareto / 权重实验。
- 1000 人压力测试。

### 阶段 3：产品化

- 后台求解任务、进度、取消。
- 数据版本、审计、权限。
- Excel 字段兼容真实教务系统。
- 课表打印/导出 PDF 模板。
- 移动端。

### 阶段 4：DSH 插件（已完成基础版，待 Windows 实机验收）

已实现：

- 宿主插件启动内置 Python/OR-Tools sidecar，代理同源路由；
- 客户端侧边栏 + iframe 工作台；
- macOS arm64 完整 E2E；
- Windows x64 结构包 + 平台守卫。

待办：

- Windows 10/11 实机安装、求解、Excel、卸载验收；
- 如 DSH 提供官方 sidebar slot，替换 DOM 注入；
- 插件自动更新/版本兼容声明；
- 大包体积优化（可选）。

## 8. 演示脚本（5 分钟）

1. 打开总览，指向 F 场景：320 人、24 组合、62 教师。
2. 点击“一键排课”，展示 OPTIMAL、约 0.2s。
3. 打开校验页：11 项全 0，独立校验器声明。
4. 打开行政班课表：说明同一格多个教学班就是走班。
5. 打开教学班：合班、教师、教室、学生名单。
6. 打开规则页，把“走班组最多行政班”改为 2，保存，重跑。
7. 展示真实无解：“4 个物理班 vs 3 名教师”，强调没有放宽约束。
8. 切到场景 G，展示资源不足预检无解。
9. 改回 cap=0 或 reset，重跑恢复。
10. 导出 Excel，展示四类课表与校验报告。

## 9. 验收清单

- [x] 一键启动
- [x] 31 时段时间模型
- [x] 24 组合模拟数据
- [x] CP-SAT 真实求解
- [x] 独立校验器
- [x] 学生/教师/教室冲突 0
- [x] 课时缺失 0
- [x] 超容量 0
- [x] 数学交替
- [x] 物理/历史、外语、再选走班规则
- [x] 四类课表
- [x] Excel 导入导出
- [x] A-G 场景
- [x] 无解/超时区分
- [x] 文档与测试
- [x] 基础科教师绑定
- [ ] 外语/走班教学班指定教师
- [ ] 局部调课
- [x] DSH 插件 macOS arm64（安装/排课/Excel/卸载）
- [ ] DSH 插件 Windows x64 实机验收

## 10. 给接手者的一句话

不要为了让某个场景“跑通”去改硬约束。先判断是数据冲突、资源冲突还是建模假设；把结论写进 ASSUMPTIONS 和 TEST_REPORT，再决定是否调整模型。
