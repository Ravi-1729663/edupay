#!/usr/bin/env bash
# =====================================================================
# EduPay — Local Launcher Script (Linux / macOS)
# =====================================================================
set -e

echo "=========================================================="
echo "  EduPay — Fee Collection & Financial Reconciliation System "
echo "=========================================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default local database to SQLite unless PostgreSQL is explicitly specified
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT_DIR/backend/edupay_local.db}"

# 1. Check Python
echo -e "\n[1/4] Checking Python environment..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python 3 is required."
    exit 1
fi
PYTHON_CMD=$(command -v python3 || command -v python)

# 2. Setup Backend Dependencies & DB
echo "[2/4] Setting up Backend dependencies & database..."
cd "$ROOT_DIR/backend"
$PYTHON_CMD -m pip install -q -r requirements.txt 2>/dev/null || true

echo "Running database migrations..."
$PYTHON_CMD -m alembic upgrade head
echo "Seeding database with realistic demo dataset..."
$PYTHON_CMD -m app.db.seed

cd "$ROOT_DIR"

# 3. Check Node.js
echo -e "\n[3/4] Checking Node.js environment..."
if ! command -v npm &> /dev/null; then
    echo "Error: npm is required."
    exit 1
fi

if [ ! -d "$ROOT_DIR/node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# 4. Launching Services
echo -e "\n[4/4] Launching EduPay Services..."
echo "  Backend API:  http://localhost:8000  (Docs: http://localhost:8000/docs)"
echo "  Frontend SPA: http://localhost:3000"
echo -e "\nDemo Accounts (Password: Password123!):"
echo "  - System Admin:      admin@edupay.college"
echo "  - Finance Manager:   manager@edupay.college"
echo "  - Finance Staff:     staff@edupay.college"
echo "  - Student:           student@edupay.college"
echo "=========================================================="

# Start backend in background & ensure cleanup on exit
cd "$ROOT_DIR/backend"
$PYTHON_CMD -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

trap "echo 'Stopping backend...'; kill $BACKEND_PID 2>/dev/null" EXIT

cd "$ROOT_DIR"
npm run dev
