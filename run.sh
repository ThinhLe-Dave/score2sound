#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
VENV_PIP="$SCRIPT_DIR/venv/bin/pip"

if [[ ! -x "$VENV_PYTHON" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    VENV_PYTHON="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    VENV_PYTHON="$(command -v python)"
  else
    echo "Error: Python is not installed."
    exit 1
  fi
fi

if [[ ! -x "$VENV_PIP" ]]; then
  VENV_PIP="$VENV_PYTHON -m pip"
fi

function print_usage() {
  cat <<EOF
Usage: ./run.sh [command]

Commands:
  install    Create/refresh the virtualenv dependencies
  serve      Start the FastAPI service (default)
  test       Run the test suite with pytest

Examples:
  ./run.sh install
  ./run.sh serve
  ./run.sh test
EOF
}

COMMAND="${1-serve}"

case "$COMMAND" in
  install)
    echo "Installing dependencies..."
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r requirements.txt
    ;;
  test)
    echo "Running tests..."
    "$VENV_PYTHON" -m pytest tests
    ;;
  serve)
    echo "Starting score2sound service..."
    SSL_CERT_FILE="$($VENV_PYTHON -c 'import certifi; print(certifi.where())')"
    export SSL_CERT_FILE
    export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
    exec "$VENV_PYTHON" main.py
    ;;
  -*|help|--help)
    print_usage
    ;;
  *)
    echo "Error: unknown command '$COMMAND'"
    print_usage
    exit 1
    ;;
esac
