# Windows x64 插件验收清单

当前状态：**未执行**。构建机为 macOS，没有 Windows 实机/VM。以下步骤必须在 Windows 10/11 x64 上执行并记录结果。

## 1. 包完整性

```powershell
Get-FileHash .\dsh-aiwish-timetable-0.2.0.tgz -Algorithm SHA256
tar -tzf .\dsh-aiwish-timetable-0.2.0.tgz | Select-String "runtime/python.exe"
tar -tzf .\dsh-aiwish-timetable-0.2.0.tgz | Select-String "runtime/Lib/site-packages/ortools"
```

预期：

- SHA256 与 `SHA256SUMS.txt` 一致。
- 存在 `runtime/python.exe`、`python312.dll`、`_ssl.pyd`、`libssl-3.dll`。
- 存在 `ortools/.libs/ortools.dll`、numpy/pandas `.pyd`。

## 2. 内置运行时 smoke test

将包解压到临时目录，执行：

```powershell
.\runtime\python.exe -c "import ortools, numpy, pandas, fastapi, openpyxl; from ortools.sat.python import cp_model; m=cp_model.CpModel(); x=m.NewIntVar(0,2,'x'); m.Maximize(x); s=cp_model.CpSolver(); print(ortools.__version__, s.StatusName(s.Solve(m)), s.Value(x))"
```

预期：

```text
9.15.6755 OPTIMAL 2
```

## 3. DSH 安装

```powershell
dsh plugin --profile desktop add C:\path\dsh-aiwish-timetable-0.2.0.tgz
dsh --profile desktop
```

- DSH 启动无 "unsupported-platform"。
- 侧边栏出现「智能排课」。
- 打开后 iframe 显示工作台。
- `/plugins/aiwish/diag` 中 `platform=win32`，`python` 指向 `runtime\python.exe`。

## 4. 功能

- 场景 F 加载：320 学生、24 组合。
- 一键排课：`OPTIMAL`，独立校验通过。
- 场景 G：预检无解，不生成课表。
- Excel：模板下载、导出、导入、重新求解。
- 学生/教师/课程/教室/规则页面可打开。
- 控制台无 error。

## 5. 路径与权限

- 数据目录：`%USERPROFILE%\.dsh\plugin-data\dsh-aiwish-timetable\`
- 日志：`server.log`
- 不需要管理员权限，不修改系统 Python。
- 如遇 Windows Defender/SmartScreen 拦截，记录文件名、签名状态和事件日志；不要直接关闭安全软件。

## 6. 卸载

```powershell
dsh plugin --profile desktop remove dsh-aiwish-timetable
```

- 重新启动 DSH 后侧边栏入口消失。
- `/plugins/aiwish/*` 返回 404。
- 数据目录保留（符合预期）。

## 7. 需要记录

- Windows 版本、DSH 版本。
- tgz SHA256。
- 安装耗时、首次打开耗时。
- 排课耗时与校验结果。
- 任何错误截图、`server.log`、DSH 日志。
- 是否出现杀毒/防火墙提示。

完成后把结果补入 `PLUGIN_TECH_VALIDATION.md` 和 `TEST_REPORT.md`。
