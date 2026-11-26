# DSH 插件适配计划（2026-11-26 更新：已实现插件包）

> **状态更新**：本文件最初是预留计划；2026-11-26 已完成 DSH 0.2.2-rc.1 的协议验证、macOS 端到端插件包和 Windows 结构构建。实际结果见根目录 `PLUGIN_TECH_VALIDATION.md`。本文件保留为设计与后续计划参考。

## 1. 结论先行

**已完成**：DSH 0.2.2-rc.1 插件包，内置 Python/OR-Tools，侧边栏「智能排课」。macOS arm64 已实测安装、排课、校验、Excel、卸载；Windows x64 已构建但未实机运行。

真正适配前必须：

1. 检查当前 DSH 版本的插件协议、工具注册方式、权限模型；
2. 找到并阅读本机已有“会议记录”插件的成熟实现；
3. 复用其工具声明、确认交互、数据存储与隐私边界；
4. 再写适配层。

不要凭记忆假设 DSH 插件 API。不同版本的 manifest、工具 schema、UI 面板协议可能不同。


## 1.1 本机检查结果（2026-11-25）

已实际查看本机会议记录插件 `~/Desktop/个人相关/player/meeting-notes/plugin`（v0.6.4）的结构，仅作为协议参考，不复制业务代码：

- npm 包名 `dsh-meeting-notes`，`type: module`，主入口 `lib/index.js`，客户端入口 `lib/client.js`。
- `package.json` 通过 `dsh.bundle.patch` 指向 `cordis.patch.yml`，通过 `dsh.client.platform = "web"` 声明 Web 客户端。
- 资源：`app/` 静态页面、`locale/` 中英文、`icon.svg`、`docs/`、`cordis.patch.yml`。
- 运行数据放在 `~/.dsh/plugin-data/<plugin-name>/`。
- 本机通过 `dsh plugin --profile desktop add ./dist/<pkg>.tgz` 安装。
- 本机 profile 配置在 `~/.dsh/profiles/desktop/`，插件管理数据在 `.plugin-manager/`。

这些信息说明：未来 AI-WISH 适配应当采用同样的 **npm 包 + cordis patch + host/client 入口 + 本地 plugin-data** 结构，但具体 schema 仍需按安装时的 DSH 版本确认，不能直接照抄会议插件。

## 2. 目标架构

```text
DSH 对话
  │  工具调用（JSON schema）
  ▼
dsh-aiwish adapter（未来）
  │  只做参数映射、确认、权限、结果格式化
  ▼
engine/aiwish/tools.py
  │
  ├── data_gen / import
  ├── analysis
  ├── rules
  ├── builder + solver
  ├── validator
  └── export
```

禁止：

- 在 adapter 里复制 CP-SAT 模型；
- 在 adapter 里直接改 SQLite 绕过校验；
- 把整份学生表/教师表塞进模型上下文；
- 用自然语言直接关闭硬约束。

## 3. 工具接口映射

`engine/aiwish/tools.py` 已提供 9 个工具：

| 工具 | 需求中的能力 | 当前实现 | DSH 适配注意 |
|---|---|---|---|
| `import_basic_data` | 导入基础数据 | 校验学生/教师/教室/课程 | 文件解析先落本地，不把明细发模型 |
| `analyze_selection` | 分析学生选科 | 24 组合、外语、容量预警 | 只返回聚合数据 |
| `get_rules` | 查询规则 | 硬约束/待确认/权重 | 可安全直出 |
| `update_rules` | 修改规则 | 参数校验；`confirmed=False` 返回确认请求 | 重要变更必须二次确认 |
| `run_auto_schedule` | 执行自动排课 | CP-SAT + 独立校验 | 同步可能耗时；DSH 中可加超时/后台 |
| `get_schedule` | 查询结果 | 任务/教学班/校验 | 大结果分页/摘要 |
| `diagnose_conflicts` | 诊断冲突 | 重新校验、预检原因 | 返回违规摘要，不返回全部学生明细 |
| `reschedule_partial` | 局部调课 | **未实现**，返回 `supported:false` | 不得伪造成功 |
| `export_timetable` | 导出课表 | JSON 四类视图 | Excel 由 Web 适配层生成，或新增本地导出工具 |

## 4. 自然语言修改规则的确认流程

```text
用户："把物理走班组限制改成最多两个行政班"
        │
        ▼
adapter/本机模型：解析为结构化 patch
  {"walk_group_admin_class_cap": 2}
        │
        ▼
update_rules(scenario, patch, confirmed=False)
  ├─ validate_rule_patch 类型/范围校验
  └─ requires_confirmation: true
        │
        ▼
DSH 向用户展示影响：
  - 该规则来自"待确认"需求
  - 启用后 F 场景会因 3 名物理教师而证明无解
        │
    用户确认
        │
        ▼
update_rules(scenario, patch, confirmed=True)
        │
        ▼
重新运行 run_auto_schedule
```

任何一步失败都返回明确错误，不落库。

## 5. 隐私边界

- 学生、教师姓名、工号、不可排时间默认只在本机 SQLite/内存中处理。
- 不把学生明细、教师明细、完整课表发送给远程大模型。
- 若需要自然语言规则解析，只发送：
  - 规则键；
  - 当前值；
  - 可选值/范围；
  - 不发送学生/教师个人数据。
- 分析结果只返回聚合统计（人数、组合数、容量预警）。
- 导出文件保存在本地；上传/共享由用户显式操作。

## 6. 数据与状态

V0.1 的 SQLite：

- `scenarios(id, payload, updated_at)`
- `runs(id, scenario_id, status, solver_status, created_at, scenario_updated_at, payload)`

DSH 适配时可复用本地 API，或直接调用 engine。若直接调用 engine：

- 场景快照由 adapter 自己管理；
- 运行历史由 adapter 管理；
- 必须保留 `scenario_updated_at` 与 `is_stale` 语义；
- 不能让用户看到“改完数据但旧课表仍显示为当前结果”。

## 7. 插件 UI 预留

如果 DSH 支持面板/侧栏：

- 场景选择；
- 最近求解状态；
- 一键排课；
- 校验通过/违规；
- 课表视图入口；
- 规则确认卡片。

V0.1 的 React 工作台已覆盖这些信息，可作为插件 WebView 或独立页面复用。

## 8. 分阶段计划

### 前检查（必须）

- [ ] 读取当前 DSH 插件文档；
- [ ] 查看 `~/.dsh` 插件目录与 manifest 示例；
- [ ] 阅读会议记录插件源码/文档；
- [ ] 确认工具 schema、确认 UI、本地文件访问权限；
- [ ] 确认是否允许运行本地 Python 子进程。

### MVP

- [ ] 只读工具：`get_rules`、`analyze_selection`、`get_schedule`、`diagnose_conflicts`；
- [ ] 求解工具：`run_auto_schedule`；
- [ ] 规则修改：确认流程；
- [ ] 场景选择；
- [ ] 本地数据，不上传明细。

### 后续

- [ ] Excel 导入导出；
- [ ] 局部调课；
- [ ] 面板 UI；
- [ ] 多场景管理；
- [ ] 权限与审计。

## 9. 不在本阶段做的事

- 不猜 DSH manifest 字段；
- 不复刻会议记录插件的 UI，只复用模式；
- 不把 engine 改造成依赖 DSH；
- 不在 adapter 里写第二套排课逻辑。

## 10. 参考资料

- 当前 DSH 版本：由运行时上下文给出，适配时重新确认。
- 本机已有插件：以 `~/.dsh` 与 DSH 设置页为准。
- 会议记录插件：优先参考其工具注册、确认交互、数据落地方式。
