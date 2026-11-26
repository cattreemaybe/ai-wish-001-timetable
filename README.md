# AI-WISH-001 · 新高考智能走班排课工作台

**核心 V0.1 · DSH 插件 0.2.1**

GitHub: [cattreemaybe/ai-wish-001-timetable](https://github.com/cattreemaybe/ai-wish-001-timetable) · Release: [v0.2.1](https://github.com/cattreemaybe/ai-wish-001-timetable/releases/tag/v0.2.1)

一个可运行、可验证、可演示的新高考排课原型。它使用 **OR-Tools CP-SAT** 真实求解 31 个教学时段的课程安排，并由一个**不导入求解器模型**的独立校验器复核硬约束。

> 本项目来自「DeepSeek改变世界」AI 许愿机栏目。V0.1 的目标不是商业化产品，而是把真实算法、数据模型、工作台和验证证据交给需求提出者试用与反馈。

![DSH 插件中的排课工作台](docs/screenshots/dsh-plugin.png)

## 0. DSH 插件形态（优先交付）

产品优先以 **DSH 插件**交付：用户安装 DSH 后导入插件包，无需安装 Python、Node、OR-Tools 或配置服务器。插件自带平台 Python 运行时、OR-Tools、FastAPI 与 React 工作台，本地启动，不调用大模型 API。

| 平台 | 原生安装包（DSH 使用） | 分发包装 |
|---|---|---|
| macOS arm64 | [dsh-aiwish-timetable-0.2.1-darwin-arm64.tgz](https://github.com/cattreemaybe/ai-wish-001-timetable/releases/download/v0.2.1/dsh-aiwish-timetable-0.2.1-darwin-arm64.tgz)（约 82MB） | [ZIP](https://github.com/cattreemaybe/ai-wish-001-timetable/releases/download/v0.2.1/AI-WISH-001-DSH-darwin-arm64.zip) |
| Windows x64 | [dsh-aiwish-timetable-0.2.1-win32-x64.tgz](https://github.com/cattreemaybe/ai-wish-001-timetable/releases/download/v0.2.1/dsh-aiwish-timetable-0.2.1-win32-x64.tgz)（约 59MB） | [ZIP](https://github.com/cattreemaybe/ai-wish-001-timetable/releases/download/v0.2.1/AI-WISH-001-DSH-win32-x64.zip) |

安装：

1. 解压 ZIP（如果拿到的是 ZIP）；
2. 在 DSH 的「插件」页面安装其中的 `.tgz`；
3. 启用并刷新窗口；
4. 侧边栏点击「智能排课」。

命令行等价：

```bash
dsh plugin --profile desktop add /absolute/path/dsh-aiwish-timetable-0.2.1.tgz
```

**重要协议限制**：DSH 0.2.2-rc.1 的插件管理器只接受 npm tarball（`.tgz`）、本地目录、npm 包名和 Git 地址，**不支持把 `.zip` 直接作为安装源**。因此 ZIP 只是分发包装，不能声称可被 DSH 直接导入。

- 技术验证：[PLUGIN_TECH_VALIDATION.md](PLUGIN_TECH_VALIDATION.md)
- 插件构建说明：[dsh-plugin/README.md](dsh-plugin/README.md)
- Windows 验收清单：[PLUGIN_WINDOWS_ACCEPTANCE.md](PLUGIN_WINDOWS_ACCEPTANCE.md)

### 已验证 / 未验证

- macOS Apple Silicon：安装、侧边栏、iframe、排课、独立校验、Excel 导入导出、卸载全部实测通过。
- Windows x64：包结构、平台声明、Python/OR-Tools DLL 结构检查通过；**无 Windows 实机，未执行运行验证**。
- 插件 UI 通过 DSH 侧边栏 DOM 注入 + 同源 iframe；DSH 升级后需回归。

## 0.1 教务老师怎么使用（V0.1 UX 优化）

### 第一次打开

工作台提供两个明确选择：

- **使用示例数据体验**：直接加载综合场景 F，所有示例数据在顶部和首页都有「示例数据」标记；
- **创建自己的排课方案**：从空白方案开始，示例数据不会被当成学校数据。

### 首页「排课准备」

首页新增排课准备区，按老师的工作顺序列出 6 项：

1. 学生与选科
2. 教师与任课
3. 教室资源
4. 课程与课时
5. 上课时间
6. 排课规则

每项显示当前数量、缺失信息和直接入口。点击「排课前检查」后，系统会用普通老师能理解的语言区分：

- 数据配置不完整
- 教师/教室资源不足
- 资源可行，可以自动排课

只有检查通过（或只有非阻断提示）才建议点击「自动排课」。

### 分项 Excel 导入

学生、教师、教室、课程页面顶部都提供：

- 下载本类别 Excel 模板
- 导入本类别 Excel
- 手动新增
- 编辑现有数据

分项导入只更新该类别，**不会覆盖其他类别**；整套备份/恢复仍在「Excel 数据交换」页。

导入后会显示成功数量、失败行、重复数据、缺失字段及原因。导入失败时不写入，原方案保持不变。

### 高级设置

时间上限、worker、软约束权重放在自动排课页的「高级算法参数」折叠区，普通用户保持默认即可。

#### 验收路径

- 路径 A：首次打开 → 示例数据 → 排课前检查 → 自动排课 → 查看课表 → 导出 Excel；
- 路径 B：创建自己的方案 → 下载/导入学生、教师、教室 → 检查课程与规则 → 自动排课 → 查看并导出。

两条路径均已用浏览器自动化走通，详见 [TEST_REPORT.md](TEST_REPORT.md#15-v01-工作台-ux-验收)。

## 1. 独立源码运行（保留形态）

独立源码形态用于开发、测试和未来独立软件。它仍然保留，并且排课核心与 DSH 插件完全共用。

### 环境

- macOS / Linux，Python 3.11+（含 SSL）
- Node.js 20+，pnpm
- 本地运行，不需要 GPU，不调用付费 API

### 一键启动

```bash
cd AI-WISH-001
./start.sh
```

打开 <http://127.0.0.1:8000>。首次启动会创建 `.venv`、安装 Python 依赖并构建前端；之后启动会复用缓存。

如果本机默认 `python3` 的 SSL 损坏（例如部分 conda 环境），`start.sh` 会自动寻找 Homebrew Python。也可以显式指定：

```bash
PYTHON=/opt/homebrew/bin/python3.13 ./start.sh
```

### 开发模式

```bash
./dev.sh
# 前端 http://127.0.0.1:5173
# API  http://127.0.0.1:8000
```

### 测试

```bash
./test.sh
# 或
PYTHONPATH=engine:backend .venv/bin/pytest
```

### 核心 CLI（不依赖网页/API）

```bash
PYTHONPATH=engine .venv/bin/python -m aiwish.cli list
PYTHONPATH=engine .venv/bin/python -m aiwish.cli run F --summary
PYTHONPATH=engine .venv/bin/python -m aiwish.cli run F --out data/F_result.json
PYTHONPATH=engine .venv/bin/python -m aiwish.cli validate data/F_result.json
```

## 2. 已实现的能力

### 排课核心

- 学生选科：外语、首选（物理/历史）、再选（四选二），支持 24 种外语×选科组合。
- 课程课时：语文 5、数学 8、外语 6、首选 4、两门再选各 4，合计 31 节。
- 教师 62 人：10 个学科候选池、不可排时间、周课时上限校验；基础科支持按行政班绑定教师。
- 教室 26 间：30 / 45 / 60 座，容量硬约束与时间冲突。
- 31 个教学时段：周一至周五 + 周六/周日非标准安排，非教学时段不排课。
- 分阶段建班：行政班基础课、外语教学班、首选走班、再选两段走班。
- 真实时间求解：CP-SAT 接收全部任务、教师、教室、学生与时段约束。
- 求解状态严格区分：`OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN / MODEL_INVALID / PRECHECK_INFEASIBLE`。
- 独立校验器：学生/教师/教室冲突、课时、容量、教师不可排、每日上限、数学交替、走班规则、四视图一致性。
- 指标：求解耗时、走班学生、走班人次、合班数、教学班数、教师空堂、平均班额等。

### 工作台（中文）

- 排课总览、自动排课、求解状态、运行记录
- 学生及选科管理（编辑 + 搜索 + 分页）
- 教师及不可排时间管理（42 个网格时段可视化选择、基础科教师绑定）
- 课程课时配置（细分课程与周课时）
- 教室资源管理
- 时间模型查看与 JSON 编辑
- 走班教学班详情（教师、教室、学生名单、上课时段）
- 排课规则与软约束权重
- 行政班 / 学生 / 教师 / 教室四类课表
- 校验报告与违规明细
- Excel 模板下载、导入、带四类课表和校验报告的导出

## 3. 算法怎么工作

```text
学生/教师/教室/课程/时间模型
        │
        ▼
分阶段建班（builder.py）
  1. 行政班语文、数学
  2. 外语按语言跨班建班
  3. 首选物理/历史平行段
  4. 再选科目按固定顺序拆 A/B 两段
  5. 教师/教室预分配与容量检查
        │
        ▼
CP-SAT 时间求解（solver.py）
  - 每任务恰好一个时段
  - 学生/教师/教室 NoOverlap
  - 教师不可排时间过滤
  - 同班同科每日 ≤2
  - 数学 8 个任务严格按 L,P,L,P... 递增
  - 软约束目标函数
        │
        ▼
独立校验（validator.py，不导入 solver）
        │
        ▼
四类课表 / Excel / 指标 / 报告
```

关键点：**没有预先写好的课表**。教学班划分和资源分配是显式的前置决策；具体每个任务放在哪个时段完全由 CP-SAT 决定。

### 时间分块

| 阶段 | 时段数 | 组织方式 |
|---|---:|---|
| 基础段 | 13 | 每个行政班语文 5 + 数学 8 |
| 外语段 | 6 | 英语/日语跨班教学班 |
| 首选段 | 4 | 物理、历史同步走班 |
| 再选 A 段 | 4 | 按科目顺序的前半科目 |
| 再选 B 段 | 4 | 按科目顺序的后半科目 |

再选科目固定顺序为 `生物 → 化学 → 地理 → 政治`。每名学生的两门再选，较早的一门进入 A 段，较晚的一门进入 B 段。因此 A 段最多 3 科、B 段最多 3 科，**不会出现四科同时走班**。

## 4. 模拟场景与真实结果

固定随机种子生成，数据不是围绕预设课表反向构造的。

| 场景 | 内容 | 学生 | 结果 | 求解 | 教学班 | 走班学生 | 合班 | 校验 |
|---|---|---|---:|---|---:|---:|---:|---:|---|
| A | 无走班普通行政班 | 40 | OPTIMAL | 0.026s | 6 | 0 | 0 | 通过 |
| B | 班内两种选科组合 | 40 | OPTIMAL | 0.028s | 9 | 40 | 0 | 通过 |
| C | 两班物理历史同步走班 | 80 | OPTIMAL | 0.045s | 12 | 80 | 2 | 通过 |
| D | 四选二两科/三科走班 | 80 | OPTIMAL | 0.048s | 14 | 80 | 8 | 通过 |
| E | 英语日语混合走班 | 80 | OPTIMAL | 0.045s | 12 | 80 | 8 | 通过 |
| F | 综合场景 8 班 320 人 | 320 | OPTIMAL | 0.161s | 41 | 320 | 25 | 通过 |
| G | 故意资源不足 | 320 | PRECHECK_INFEASIBLE | — | 0 | — | — | 无课表，不放宽约束 |

> 求解时间与机器、worker 数有关；上表来自本机一次真实运行。

### 综合场景 F

- 8 个行政班、320 名学生、24 种外语×选科组合、62 名教师、26 间教室。
- 41 个教学班，218 个周任务，9,920 条学生-课时记录。
- 18 个走班教学班，25 个跨行政班合班。
- 走班学生 320 人，走班总人次 640。
- 教师空堂 0 节（在目标函数下）。
- 平均班额 46.8，最大班额 54（60 座教室）。
- 独立校验器：全部 11 项核心计数为 0，**0 硬约束违规**。

### 无解场景 G

综合场景变体只保留 **1 名物理教师**。物理 162 名学生、教室上限 60 人，至少需要 3 个教学班同时开课，但只有 1 名教师：

```text
数据预检证明无解：162 名学生最多只能拆成 1 个教学班，按最大教室 60 人仍超出容量
```

系统没有生成假课表，没有放宽容量，也没有把这类情况标成“超时”。

## 5. 独立校验器

`engine/aiwish/validator.py` **不导入** `solver.py` 或 `builder.py`。它从场景、教学班元数据和最终任务列表重新检查：

- 学生时间冲突 = 0
- 教师时间冲突 = 0
- 教室时间冲突 = 0
- 学生规定课时缺失 = 0
- 教室超容量 = 0
- 教师不可排时间违规 = 0
- 同一天同科 ≤ 2
- 数学正/落实课按周内顺序交替
- 首选段只出现物理/历史
- 外语段只出现英语/日语
- 再选每段最多 3 科，绝不 4 科
- 四类视图条目与任务源一致

## 6. 项目结构

```text
AI-WISH-001/
├── engine/aiwish/          # 独立排课核心（不依赖 FastAPI/React/DSH）
│   ├── domain.py           # 数据模型、课程配置、时间模型
│   ├── data_gen.py         # A-G 固定种子模拟数据
│   ├── builder.py          # 分阶段建班、教师/教室预分配
│   ├── solver.py           # OR-Tools CP-SAT 时间求解
│   ├── validator.py        # 独立校验器
│   ├── runner.py           # 一次性运行入口
│   ├── analysis.py         # 选科/资源分析
│   ├── tools.py            # DSH 对话工具接口（保留）
│   └── cli.py              # 独立 CLI
├── backend/app/            # FastAPI + SQLite + Excel 适配层
├── frontend/               # React + TypeScript 工作台
├── dsh-plugin/             # DSH 宿主/客户端/打包脚本/运行时说明
├── dist/                   # 平台 tgz 与 ZIP 分发包装
├── backend/tests/          # 45 个自动化测试
├── docs/screenshots/       # 演示截图
├── start.sh / dev.sh / test.sh
├── PLUGIN_TECH_VALIDATION.md
├── PLUGIN_WINDOWS_ACCEPTANCE.md
├── REQUIREMENTS.md
├── ASSUMPTIONS.md
├── TEST_REPORT.md
├── DEV_LOG.md
├── HANDOFF.md
├── AGENTS.md
└── docs/DSH_PLUGIN_PLAN.md
```

## 7. API 与工具接口

### Web API

- `GET /api/scenarios`、`GET /api/scenarios/{id}`
- `POST /api/scenarios/{id}/solve`
- `GET /api/runs/{run_id}/timetable?view=admin|student|teacher|room|class&entity_id=...`
- `GET /api/runs/{run_id}/teaching-classes`
- `POST /api/runs/{run_id}/validate`
- `GET /api/scenarios/{id}/export.xlsx`
- `GET /api/excel/template?sid=F`
- `POST /api/scenarios/{id}/import?mode=replace|merge`
- 学生/教师/教室/课程/规则/时间模型的编辑接口

### 工具面（保留给 DSH 对话内工具）

`engine/aiwish/tools.py` 已预留：

1. 导入基础数据
2. 分析学生选科
3. 查询/修改排课规则（重要修改强制二次确认）
4. 执行自动排课
5. 查询课表
6. 诊断冲突
7. 局部调课与重新求解（V0.1 返回未支持，不伪造）
8. 导出课表

详见 [docs/DSH_PLUGIN_PLAN.md](docs/DSH_PLUGIN_PLAN.md)。

## 8. 重要假设与边界

完整列表见 [ASSUMPTIONS.md](ASSUMPTIONS.md)，最关键的几条：

1. **31 个教学时段、每名学生 31 节**：因此每名学生每周正好填满所有时段，没有空堂。这个模型很紧；任一行政班的语文和数学教师若在同一时段都不可用，该班学生将无课可上。模拟数据因此只给数学教师生成不可排时间。
2. **再选科目分 A/B 两段**：固定顺序保证每段最多 3 科，但也会牺牲部分“两科走班优先”的灵活性。D/F 场景实际出现 3 科并行。
3. **“物理/历史走班组最多两个行政班”默认未启用**：需求原文标注“待确认”。本机实测，启用后综合场景 F 需要 4 个物理教学班，但只有 3 名物理教师，**证明无解**。系统会如实报告，不会偷偷关闭该规则。
4. **教师绑定**：基础科已支持按行政班指定教师；外语/走班教学班绑定键已在数据层预留，但尚无完整业务规则和 UI。
5. **教室在求解前分配**：求解器仍检查教室时间冲突与容量，但教室选择是分阶段启发式，而不是联合优化。
6. **单周静态课表**：不支持学期内教师变动、临时调课、局部重排。
7. **学生数据与教师数据只在本机 SQLite / 内存中处理**，不上传大模型。

## 9. 已知限制 / 下一阶段

- “局部调课 + 重新求解”只有工具接口占位，没有算法实现。
- 外语/走班教学班的指定教师 UI 与候选范围规则还需业务确认（基础科已支持行政班绑定）。
- 走班组两个行政班的严格约束与现有 3 名物理教师资源冲突，需要需求方决定调整资源、班额还是规则。
- CP-SAT 在 320 人下求解很快，但尚无 1000+ 人压力测试。
- 前端为 V0.1 工作台，未做移动端深度适配。
- V0.1 未做 DSH 插件适配；先检查当前 DSH 协议与已有会议记录插件，再复用成熟经验。

## 10. 文档索引

- [REQUIREMENTS.md](REQUIREMENTS.md) — 需求来源与实现映射
- [ASSUMPTIONS.md](ASSUMPTIONS.md) — 未确认规则、模拟假设与冲突证明
- [TEST_REPORT.md](TEST_REPORT.md) — 真实测试结果、失败记录
- [DEV_LOG.md](DEV_LOG.md) — 开发过程与关键技术决策
- [HANDOFF.md](HANDOFF.md) — 项目现状、已知问题、下一阶段
- [AGENTS.md](AGENTS.md) — 给后续 Agent 的工程约定
- [PLUGIN_TECH_VALIDATION.md](PLUGIN_TECH_VALIDATION.md) — DSH 插件协议与端到端验证
- [dsh-plugin/README.md](dsh-plugin/README.md) — 插件构建与安装
- [PLUGIN_WINDOWS_ACCEPTANCE.md](PLUGIN_WINDOWS_ACCEPTANCE.md) — Windows 验收清单
- [docs/DSH_PLUGIN_PLAN.md](docs/DSH_PLUGIN_PLAN.md) — 早期 DSH 适配计划（已被验证报告更新）

---

**V0.1 的诚实边界**：算法会给出真实解或真实无解，不会用固定课表、放宽硬约束或把超时伪装成成功。
