#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHONPATH="$ROOT/engine:$ROOT/backend" .venv/bin/pytest
(cd frontend && pnpm run build)
if [ -f dist/dsh-aiwish-timetable-darwin/dsh-aiwish-timetable-0.2.0.tgz ]; then
  .venv/bin/python dsh-plugin/test/package_check.py
fi
