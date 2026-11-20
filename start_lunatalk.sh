#!/bin/sh
set -eu
APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export PYTHONPATH="$APP_DIR"
exec /usr/bin/python3 -s -m lunatalk "$@"
