#!/usr/bin/env bash
# =====================================================================
# EduPay — Test Suite Launcher (Linux / macOS)
# =====================================================================
set -e

echo "Running EduPay Backend Test Suite (pytest)..."
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD=$(command -v python3 || command -v python)

cd "$ROOT_DIR/backend"
$PYTHON_CMD -m pytest app/tests -v
