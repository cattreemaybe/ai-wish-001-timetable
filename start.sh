#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

find_python() {
  local candidates=()
  [[ -n "${PYTHON:-}" ]] && candidates+=("$PYTHON")
  candidates+=(/opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 python3.13 python3.12 python3.11 python3 /usr/bin/python3)
  for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import ssl, venv' >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c 'import ssl' >/dev/null 2>&1; then
  PY="$(find_python || true)"
  if [[ -z "$PY" ]]; then
    echo "未找到带 SSL 支持的 Python 3.11+。请安装 Homebrew Python 或设置 PYTHON=/path/to/python。" >&2
    exit 1
  fi
  rm -rf .venv
  "$PY" -m venv .venv
fi

if [[ ! -f .venv/.requirements-v1 ]]; then
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r requirements.txt
  touch .venv/.requirements-v1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "未找到 pnpm。请先安装 Node.js 20+ 与 pnpm。" >&2
  exit 1
fi

if [[ ! -f frontend/dist/index.html ]] || find frontend/src frontend/package.json frontend/vite.config.ts -newer frontend/dist/index.html -print -quit | grep -q .; then
  echo "[build] 构建前端..."
  (cd frontend && pnpm install --silent && pnpm build)
fi

export PYTHONPATH="$ROOT/engine:$ROOT/backend"
export AIWISH_DB="${AIWISH_DB:-$ROOT/data/aiwish.db}"
echo ""
echo "AI-WISH-001 排课工作台"
echo "  http://127.0.0.1:${PORT:-8000}"
echo "  数据库: $AIWISH_DB"
echo ""
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
