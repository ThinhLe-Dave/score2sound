#!/bin/bash

VENV_DIR="venv"
PYTHON_VERSION="python3.11"
VENV_PYTHON="./$VENV_DIR/bin/python"
VENV_PIP="./$VENV_DIR/bin/pip"

function create_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "📦 Creating virtual environment..."
    $VENV_PYTHON -m venv $VENV_DIR
    ./$VENV_DIR/bin/pip install --upgrade pip
    ./$VENV_DIR/bin/pip install -r requirements.txt
  fi
}

function resolve_python() {
  if [[ ! -x "$VENV_PYTHON" ]]; then
    if command -v $PYTHON_VERSION >/dev/null 2>&1; then
      VENV_PYTHON="$(command -v $PYTHON_VERSION)"
    elif command -v python3 >/dev/null 2>&1; then
      VENV_PYTHON="$(command -v python3)"
    else
      echo "Error: Python 3.11+ is required."
      exit 1
    fi
  fi
}


function help() {
  echo "Usage: ./run.sh {install|test|serve|help}"
  echo ""
  echo "Commands:"
  echo "  install : Create venv and install dependencies"
  echo "  test    : Run all tests in the tests/ directory"
  echo "  serve   : Start the local development server (FastAPI)"
  echo "  help    : Show this help message"
}

case "$1" in
  install)
    echo "📦 Setting up virtual environment..."
    resolve_python
    create_venv
    echo "✅ Setup complete! You can now run './run.sh serve' to start the server."
    ;;
  test)
    echo "🧪 Running pytest suite..."
    ./$VENV_DIR/bin/python -m pytest tests/
    ;;
  serve)
    echo "🚀 Starting FastAPI server..."
    # macOS SSL workaround for Homr checkpoint downloads
    export SSL_CERT_FILE="$(./$VENV_DIR/bin/python -m certifi)"
    export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
    ./$VENV_DIR/bin/python main.py
    ;;
    help)
    help
    ;;
    *)  
    help
    exit 1
    ;;
esac