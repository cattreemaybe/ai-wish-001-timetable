# AI-WISH 智能走班排课 · DSH 插件

安装后侧边栏出现「智能排课」。插件自带平台对应的 Python 运行时、OR-Tools、FastAPI 与前端静态资源，本地启动排课服务，不依赖系统 Python，不调用大模型 API。

## 安装

本插件包是 DSH 支持的 npm tarball（`.tgz`），不是普通 ZIP。DSH 插件管理器支持 `.tgz` 本地包、目录、npm 包名与 Git 地址；它不支持把 `.zip` 直接作为 pnpm 安装源。

在 DSH 中：

1. 打开 **设置 → 插件** 或侧边栏「插件」；
2. 选择安装本地插件，粘贴/选择 `.tgz` 文件；
3. 启用后刷新窗口；
4. 侧边栏点「智能排课」。

命令行等价：

```bash
dsh plugin --profile <profile> add /absolute/path/dsh-aiwish-timetable.tgz
```

## 数据

- 数据库：`~/.dsh/plugin-data/dsh-aiwish-timetable/aiwish.db`
- 服务日志：`~/.dsh/plugin-data/dsh-aiwish-timetable/server.log`
- 诊断：`/plugins/aiwish/diag`

所有学生、教师和排课数据默认只在本机处理。

## 平台

- macOS：`dsh-aiwish-timetable`（darwin，Apple Silicon 已验证）
- Windows：`dsh-aiwish-timetable` 的 win32 构建（x64，结构构建；实机验证见 TEST_REPORT）

## 限制

- DSH 插件协议只接受 `.tgz` npm tarball；若用户拿到 `.zip` 分发包装，需先解压出 `.tgz`。
- 插件 UI 通过 DSH 侧边栏 DOM 注入 + 同源 iframe 挂载；DSH 0.2.x 尚未提供稳定的 sidebar slot API，升级 DSH 后需回归。
- 排课核心仍是 `engine/aiwish`，与 DSH 解耦。
