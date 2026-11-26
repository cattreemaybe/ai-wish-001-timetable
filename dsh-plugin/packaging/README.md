# 运行时打包说明

## macOS（已验证）

```bash
# 1. Python 3.12.16 standalone
curl --http1.1 -L -o pbs-mac.tar.gz \
  'https://github.com/astral-sh/python-build-standalone/releases/download/20261124/cpython-3.12.16%2B20261124-aarch64-apple-darwin-install_only.tar.gz'
mkdir runtime-mac && tar -xzf pbs-mac.tar.gz -C runtime-mac --strip-components=1

# 2. wheels（在任意有网络/SSL 的 Python 里）
pip download --only-binary=:all: \
  --platform macosx_11_0_arm64 --python-version 312 \
  --implementation cp --abi cp312 --dest wheels-mac \
  ortools==9.15.6755 fastapi==0.165.0 uvicorn==0.54.0 \
  openpyxl==3.1.5 pydantic==2.14.4 python-multipart==0.0.34

# 3. 安装到内置 runtime
runtime-mac/bin/pip install --no-index --find-links wheels-mac \
  ortools==9.15.6755 fastapi==0.165.0 uvicorn==0.54.0 \
  openpyxl==3.1.5 pydantic==2.14.4 python-multipart==0.0.34

# 4. 清理测试/文档（保留 pandas/numpy，CP-SAT import 需要）
rm -rf runtime-mac/lib/python3.12/test \
       runtime-mac/lib/python3.12/idlelib \
       runtime-mac/lib/python3.12/tkinter \
       runtime-mac/lib/python3.12/turtledemo \
       runtime-mac/lib/python3.12/ensurepip \
       runtime-mac/lib/python3.12/lib2to3 \
       runtime-mac/include runtime-mac/share \
       runtime-mac/lib/python3.12/site-packages/pip \
       runtime-mac/lib/python3.12/site-packages/setuptools \
       runtime-mac/lib/python3.12/site-packages/pkg_resources
find runtime-mac -type d -name __pycache__ -prune -exec rm -rf {} +
```

验证：

```bash
runtime-mac/bin/python3 - <<'PY'
from ortools.sat.python import cp_model
m=cp_model.CpModel(); x=m.NewIntVar(0,2,'x'); m.Maximize(x)
s=cp_model.CpSolver(); print(s.StatusName(s.Solve(m)), s.Value(x))
PY
```

## Windows（结构构建，未实机运行）

```powershell
# 1. Python 3.12.10 embeddable
curl -L -o python-win.zip https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip
Expand-Archive python-win.zip runtime-win

# 2. wheels
pip download --only-binary=:all: --platform win_amd64 --python-version 312 `
  --implementation cp --abi cp312 --dest wheels-win `
  ortools==9.15.6755 fastapi==0.165.0 uvicorn==0.54.0 `
  openpyxl==3.1.5 pydantic==2.14.4 python-multipart==0.0.34

# 3. 解压 wheels
New-Item -ItemType Directory runtime-win\Lib\site-packages
Get-ChildItem wheels-win\*.whl | ForEach-Object {
  Expand-Archive $_.FullName runtime-win\Lib\site-packages
}
```

`runtime-win/python312._pth`：

```text
python312.zip
.
Lib\site-packages
import site
```

Windows 包需要包含 `python.exe`、`python312.dll`、`_ssl.pyd`、`libssl-3.dll`、`libcrypto-3.dll`、`vcruntime140*.dll`，以及 `ortools/.libs/*.dll`、numpy/pandas 的 cp312 `.pyd`。已用文件结构检查，但未在 Windows 上执行。

## 打包

```bash
.venv/bin/python dsh-plugin/packaging/stage.py \
  --platform darwin \
  --python-source /path/to/runtime-mac \
  --out dist/dsh-aiwish-timetable-darwin

.venv/bin/python dsh-plugin/packaging/stage.py \
  --platform win32 \
  --python-source /path/to/runtime-win \
  --out dist/dsh-aiwish-timetable-win32
```

## 体积

- mac 运行时解压约 194 MB，tgz 约 82 MB。
- Windows 运行时解压约 194 MB，tgz 约 59 MB。
- 主要通过 pandas/numpy/OR-Tools 原生库构成；没有下载大模型，也没有 GPU 依赖。
