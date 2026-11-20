#!/bin/sh
set -eu
APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export PYTHONPATH="$APP_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 -s "$APP_DIR/lunatalk/runtime_selector.py" "$@"
