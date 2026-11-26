# DSH 插件构建与安装

本目录是把 AI-WISH-001 打包成 DSH 插件形态的工程层。排课算法仍在 `../engine/aiwish`，没有复制到插件里。

## 已构建产物

在仓库根目录：

```text
dist/
├── dsh-aiwish-timetable-darwin/
│   └── dsh-aiwish-timetable-0.2.0.tgz      # macOS arm64，约 82 MB
├── dsh-aiwish-timetable-win32/
│   └── dsh-aiwish-timetable-0.2.0.tgz      # Windows x64，约 59 MB
├── AI-WISH-001-DSH-darwin-arm64.zip        # 分发包装（内含 tgz + 说明）
└── AI-WISH-001-DSH-win32-x64.zip
```

DSH 插件管理器只接受 npm tarball（`.tgz`）、本地目录、npm 包名和 Git 地址；**不支持把 `.zip` 直接作为 pnpm 安装源**。因此 `.zip` 只是分发包装，解压后请安装其中的 `.tgz`。

## 安装

DSH 插件页 → 安装本地插件 → 选择 `.tgz`，或：

```bash
dsh plugin --profile desktop add /absolute/path/dsh-aiwish-timetable-0.2.0.tgz
```

然后刷新 DSH 窗口，侧边栏出现「智能排课」。

## 构建

```bash
cd frontend && pnpm install && pnpm build
cd ..
.venv/bin/python dsh-plugin/packaging/stage.py \
  --platform darwin \
  --python-source /path/to/relocatable/python \
  --out dist/dsh-aiwish-timetable-darwin
```

`stage.py` 会复制：

- `lib/client.js`、`lib/index.js`
- `app/`（React 生产构建）
- `server/engine` + `server/backend/app`（未改动的核心与 API）
- `runtime/`（平台 Python + OR-Tools + FastAPI/uvicorn + openpyxl）

## 内置运行时

macOS：python-build-standalone 3.12.16（aarch64-apple-darwin），pip 安装平台 wheels。

Windows：Python 3.12.10 embeddable（win_amd64），解压 cp312 wheels 到 `Lib/site-packages`，写 `python312._pth`。

详细版本与命令见 `packaging/README.md`。

## 限制

- macOS 包只在 Apple Silicon 验证；Intel 未构建。
- Windows 包结构已构建并通过平台声明检查，但当前环境没有 Windows 实机/VM，未执行 Windows 运行验证。见根目录 `PLUGIN_TECH_VALIDATION.md`。
- 侧边栏通过 DOM 注入 + 同源 iframe；DSH 0.2.x 没有稳定的 sidebar slot API，升级需回归。
