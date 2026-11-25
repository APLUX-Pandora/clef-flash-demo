#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    echo "Missing project environment. From $ROOT run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
    exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
"$PYTHON" "$ROOT/demo/check_environment.py"
exec "$PYTHON" "$ROOT/demo/demo_server.py" "$@"
