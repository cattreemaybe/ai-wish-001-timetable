#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHONPATH="$ROOT/engine:$ROOT/backend" .venv/bin/pytest
(cd frontend && pnpm run build)
if ls dist/dsh-aiwish-timetable-darwin/*.tgz >/dev/null 2>&1; then
  .venv/bin/python dsh-plugin/test/package_check.py
fi
