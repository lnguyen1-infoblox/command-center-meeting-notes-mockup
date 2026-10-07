#!/bin/bash
# Local dev launcher: loads ../.env and runs app.py with this folder's venv.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
source "$DIR/.env"
set +a
exec "$DIR/ui/venv/bin/python" "$DIR/ui/app.py"
