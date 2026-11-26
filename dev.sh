#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/engine:$ROOT/backend"
export AIWISH_DB="${AIWISH_DB:-$ROOT/data/aiwish.db}"

if [[ ! -x .venv/bin/python ]]; then
  echo "请先运行 ./start.sh 完成依赖安装，再使用 ./dev.sh。" >&2
  exit 1
fi

.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACK_PID=$!
trap 'kill $BACK_PID 2>/dev/null || true' EXIT
(cd frontend && pnpm dev)
