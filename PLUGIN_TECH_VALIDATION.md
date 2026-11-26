# DSH 插件技术验证报告

日期：2026-11-26
DSH CLI / Desktop：**0.2.2-rc.1**
验证机：macOS 27.2，Apple Silicon（arm64）
目标：在不要求用户安装 Python、配置服务器或安装依赖的前提下，通过 DSH 插件包交付完整排课工作台。

## 1. 结论

| 问题 | 结论 |
|---|---|
| DSH 是否支持第三方插件加载 Web 页面？ | ✅ 支持。`webServer.register({ kind: 'prefix' })` + `dsh.client` 模块。 |
| 是否支持插件自带本地进程/二进制？ | ✅ 支持。DSH 宿主可 spawn 子进程；会议插件已用同样方式启动原生助手。 |
| 是否支持导入 ZIP 插件包？ | ❌ **不支持 ZIP 作为 pnpm 安装源**。DSH 接受 npm tarball（`.tgz`）、本地目录、npm 包名、Git 地址。 |
| 是否可以携带 Python + OR-Tools 运行时？ | ✅ 可以。macOS 已验证；Windows 结构构建完成。 |
| 是否必须依赖系统 Python？ | ❌ 不需要。插件包内含 Python 3.12 + OR-Tools + FastAPI + openpyxl。 |
| 是否需要大模型/Token？ | ❌ 不需要。排课、校验、Excel 全部本地完成。 |
| 是否为稳定的官方侧边栏 API？ | **不是**。当前通过 DOM 注入 + 同源 iframe 挂载，参考本机会议插件。 |

**交付决策**：

1. 以 DSH 原生 `.tgz` 作为真实安装包；
2. 额外提供 `.zip` 分发包装（内含 `.tgz` + 安装说明 + SHA256），但明确说明 DSH 不能直接导入 ZIP；
3. macOS 包（Apple Silicon）已端到端验证；
4. Windows x64 包已构建并通过平台声明检查，但当前构建机无 Windows 环境，**未实机运行验证**；
5. 侧边栏 DOM 注入方案在 DSH 0.2.2-rc.1 上验证，升级 DSH 后必须回归。

## 2. DSH 插件协议实测

### 2.1 插件声明

本机会议记录插件 `dsh-meeting-notes@0.6.4` 提供了可直接参考的结构：

```json
{
  "name": "dsh-meeting-notes",
  "type": "module",
  "main": "lib/index.js",
  "exports": { ".": "./lib/index.js", "./client": "./lib/client.js" },
  "dsh": {
    "bundle": { "patch": "./cordis.patch.yml" },
    "client": { "inject": [], "platform": "web" }
  }
}
```

`cordis.patch.yml`：

```yaml
- insert:
    - id: meeting-notes
      name: dsh-meeting-notes
```

本插件采用同样结构：

```yaml
- insert:
    - id: aiwish-timetable
      name: dsh-aiwish-timetable
```

### 2.2 宿主能力

从 `@deepseek-ai/dsh-host-webserver` 与会议插件源码确认：

- 宿主插件导出 `inject = ['webServer']`、`apply(ctx)`。
- `ctx.webServer.register({ kind: 'prefix', path: '/plugins/aiwish', handler })` 注册同源 HTTP 路由。
- 宿主插件可以 spawn 子进程；会议插件通过 `ctx.subprocess` 或 `node:child_process` 启动原生助手。
- 浏览器端模块通过 `window.__ModuleLoader__.load({ id, factory })` 注册，导出 `apply/inject/name`。
- 没有发现稳定的 sidebar slot API；会议插件通过 `[class*="sidebarCol"]` 选择器插入按钮，并在中心列挂载 iframe。本插件沿用该模式。

### 2.3 安装格式

`@deepseek-ai/dsh-plugin-manager` 的安装规格为：

- npm 包名；
- 本地目录；
- Git 地址；
- tarball（`.tgz` / `.tar.gz`，本地或 URL）。

**没有 ZIP 分支**。`pnpm add ./plugin.zip` 不会被识别为插件包。因此不能声称“DSH 支持导入 ZIP”。

### 2.4 平台声明

`dsh.bundle.platforms` 在启动器和插件管理器中选择/组合前检查。

- macOS 包：`["darwin"]`
- Windows 包：`["win32"]`

实测在 macOS 上安装 Windows 包，DSH 拒绝激活：

```text
dsh: bundle activation rejected: dsh-aiwish-timetable:
Bundle supports Host platforms win32; the DSH Host is running darwin
```

说明平台保护生效。

## 3. 运行时打包方案

### 3.1 macOS（已验证）

- Python：python-build-standalone **3.12.16**（aarch64-apple-darwin）
- wheels：ortools 9.15.6755、fastapi 0.165.0、uvicorn 0.54.0、openpyxl 3.1.5、pydantic 2.14.4、python-multipart 0.0.34
- 运行时解压约 **194 MB**
- 插件 tgz 约 **82 MB**
- 实测：

```text
ortools 9.15.6755
CP-SAT: OPTIMAL 2
```

### 3.2 Windows（结构构建，未实机运行）

- Python：3.12.10 embeddable（win_amd64）
- 将 cp312 win_amd64 wheels 解压到 `Lib/site-packages`
- `python312._pth`：

```text
python312.zip
.
Lib\site-packages
import site
```

结构检查：

- `python.exe`：PE32+ x86-64
- `python312.dll`、`_ssl.pyd`、`libssl-3.dll`、`libcrypto-3.dll`、`vcruntime140*.dll`
- OR-Tools `.libs/ortools.dll` 等原生 DLL
- 85 个 `.pyd`
- numpy/pandas/ortools 均为 cp312-win_amd64

**未验证**：没有 Windows 实机或虚拟机，无法执行 `python.exe -m app.plugin_server`、OR-Tools 求解和 DSH Windows 客户端测试。

### 3.3 体积与启动

- macOS 首次打开插件：侧边栏 → 点击「智能排课」→ iframe 加载并启动 sidecar，约数秒。
- 运行时全部解压在插件目录；不写系统 Python、不需要管理员权限。
- 数据只写 `~/.dsh/plugin-data/dsh-aiwish-timetable/`。

## 4. macOS 端到端验证

测试使用隔离的 `DSH_HOME=/tmp/dsh-aiwish-bundle`，避免污染本机桌面 profile。

### 4.1 安装

```bash
DSH_HOME=/tmp/dsh-aiwish-bundle \
  dsh --profile aiwish --from-default-profile web --dump-config

DSH_HOME=/tmp/dsh-aiwish-bundle \
  dsh plugin --profile aiwish add \
  dist/dsh-aiwish-timetable-darwin/dsh-aiwish-timetable-0.2.1.tgz
```

结果：

```text
+ dsh-aiwish-timetable 0.2.1
Done in 1.8s
```

profile 的 bundle 列表自动追加 `dsh-aiwish-timetable`。

### 4.2 启动与 sidecar

```bash
DSH_HOME=/tmp/dsh-aiwish-bundle \
  dsh --profile aiwish --port 8012 --no-open
```

诊断接口 `/plugins/aiwish/diag` 返回：

```json
{
  "plugin": "aiwish-timetable",
  "platform": "darwin",
  "arch": "arm64",
  "python": ".../node_modules/dsh-aiwish-timetable/runtime/bin/python3",
  "running": true,
  "last_error": ""
}
```

说明使用的是**插件内置 Python**，不是系统 Python。

### 4.3 侧边栏与 iframe

Playwright（Chrome）实测：

- `[data-dsh-aiwish-entry]` 数量 = 1，侧边栏出现「智能排课」。
- 点击后 `[data-dsh-aiwish-panel]` 打开，iframe `src=/plugins/aiwish/app/index.html`。
- iframe 内 `h1 = 新高考智能走班排课工作台`。
- 场景选择 F，320 人、24 组合加载正常。
- 未发现 console error / pageerror。

截图：`docs/screenshots/dsh-plugin.png`

> 在隔离 profile 中，DSH 首次启动会显示登录/API Key 的「开始使用」引导弹窗，遮罩会拦截 iframe 的鼠标事件。这是 DSH 账户引导，不是插件问题；测试时移除该引导遮罩后，用 JS 触发排课按钮完成验证。实际已登录用户的 DSH 中不会出现该拦截。

### 4.4 排课与校验

- 点击「一键排课」→ 状态从「未求解」变为「已找到最优解」。
- 校验页：「全部硬约束通过」，218 任务、320 学生、62 教师、26 教室。
- 独立校验 11 项全 0。
- 截图：`docs/screenshots/dsh-plugin.png`

### 4.5 Excel 导入/导出

通过插件路由实测：

```text
GET /plugins/aiwish/api/scenarios/F/export.xlsx
→ 200，368,333 bytes，openpyxl 可读，11 个工作表

POST /plugins/aiwish/api/scenarios/F/import?mode=replace
multipart file=export.xlsx
→ 200，students=320

POST /plugins/aiwish/api/scenarios/F/solve
→ OPTIMAL，validation=true，218 tasks
```

代理支持 multipart 上传与二进制下载。

### 4.6 卸载

```bash
DSH_HOME=/tmp/dsh-aiwish-bundle \
  dsh plugin --profile aiwish remove dsh-aiwish-timetable
```

结果：

- 插件依赖从 profile 删除；
- bundle 从选择列表删除；
- 重新启动 DSH 后 `/plugins/aiwish/api/health` 返回 **404**；
- 说明宿主路由随插件卸载移除。

插件数据目录保留，避免误删用户排课数据。

## 5. 安全与隐私

- 宿主只绑定 `127.0.0.1`。
- sidecar 只绑定 `127.0.0.1` 的 OS 随机端口，不监听外网。
- 浏览器通过同源 `/plugins/aiwish/*` 访问，不暴露 sidecar 端口给页面。
- 所有学生/教师/课表数据只在本机 SQLite：`~/.dsh/plugin-data/dsh-aiwish-timetable/aiwish.db`。
- 不调用任何大模型 API，不产生 Token。
- 插件不收集遥测。
- `/plugins/aiwish/diag` 只返回启动状态和最近日志，不含学生/教师明细。

## 6. 已知限制与风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| ZIP 不能直接安装 | DSH 只接受 `.tgz`/目录/npm/Git | 提供 `.tgz` + ZIP 分发包装 + 安装说明 |
| 侧边栏 DOM 注入 | 不是稳定官方 slot API，DSH UI 改版可能失效 | 选择器多级回退 + MutationObserver；升级 DSH 回归 |
| Windows 未实机验证 | 无 Windows VM/机器 | 已做平台声明、PE/DLL/wheel 结构检查；需在 Windows 上执行验收清单 |
| macOS 仅 arm64 | 未构建 Intel 包 | 需要时用相同流程构建 x86_64 |
| 包体积大 | 内置 Python + OR-Tools，tgz 59-82MB | 可接受；无系统依赖 |
| 首次启动数秒 | sidecar 启动 + 健康检查 | iframe 显示“正在启动本地排课服务…” |
| 本地 tarball 路径依赖 | profile 的 dependency 记录 `file:/path/*.tgz` | 安装后包已复制到 node_modules；重装需保留 tarball 或发布 npm |
| 插件数据不随卸载删除 | 防止误删课表 | 文档说明路径，用户可手动清理 |
| DSH 版本兼容 | 未声明 `engines.dsh`，在 0.2.2-rc.1 测试 | 升级后回归；必要时声明兼容范围 |
| 未代码签名/公证 | macOS/Windows 可能弹 Gatekeeper/SmartScreen | 首次运行由用户明确允许；正式发布时补签名 |

## 7. 未验证项（必须明确）

1. Windows x64 上安装 DSH、加载插件、启动 Python、OR-Tools 求解、Excel 导出、卸载。
2. macOS Intel。
3. DSH 0.3+ 的客户端 slot/侧边栏协议。
4. 插件在 DSH 桌面端与 Web 端之外的其他宿主形态（TUI/headless）。
5. 大规模数据（1000+ 学生）在插件环境中的启动/求解时间。

这些未验证项不能写成“已支持”。

## 8. 下一步

1. 在 Windows 10/11 x64 实机执行 `PLUGIN_WINDOWS_ACCEPTANCE.md` 清单。
2. 如 DSH 后续提供官方 sidebar slot API，替换 DOM 注入。
3. 如需 npm 发布，`dsh-aiwish-timetable@0.2.1` 可直接发布；平台包可用同版本不同 dist-tag/包名或按平台分仓库。
4. 为 Windows 包补自动化 CI（Windows runner）构建 + smoke test。
5. 继续完善教师绑定、局部调课等业务能力。

## 9. GitHub 发布

- 仓库：https://github.com/cattreemaybe/ai-wish-001-timetable
- Release：https://github.com/cattreemaybe/ai-wish-001-timetable/releases/tag/v0.2.1
- Release assets：两个平台 ZIP、两个平台 tgz、安装说明与校验和。

## 10. 交付文件与校验和

```text
ec5c935342bea73c0cd5eef97c981a2a5b1bc03263a4a313533c429cdbc2a7ac  dsh-aiwish-timetable-darwin/dsh-aiwish-timetable-0.2.1.tgz
e6d4f4a39eb93347adc09da57fec63c560bbab2c3aff14850dd41799ea34363b  dsh-aiwish-timetable-win32/dsh-aiwish-timetable-0.2.1.tgz
d9793dbd22f523ef16b54c813c16bdee2cf67cecdebbaf723753e693b192b3ce  AI-WISH-001-DSH-darwin-arm64.zip
0ee1372f585c3c32f321cea0a8d625920d8543eac003343321a119e274b26d41  AI-WISH-001-DSH-win32-x64.zip
```
