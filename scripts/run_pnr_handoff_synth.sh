#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec make preflight synthesis timing "$@"
