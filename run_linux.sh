#!/bin/bash
set -e

# Resolve directory this script is in
DIR="$(cd "$(dirname "$0")" && pwd)"

VENV="$DIR/venv"
PY_SCRIPT="$DIR/krossbones.py"

# Create venv if needed
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

# Ensure dependency is installed
"$VENV/bin/python" - <<'EOF'
try:
    import Pillow
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
EOF

# Run the Python script
exec "$VENV/bin/python" "$PY_SCRIPT"
