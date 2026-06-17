#!/usr/bin/env bash
#
# Executive Copilot — Start Backend & Frontend
# ==============================================
# Usage:  ./start.sh
#
# Starts both:
#   - Backend  → http://localhost:8000  (FastAPI + uvicorn)
#   - Frontend → http://localhost:5173  (Vite dev server)
#
# Prerequisites:
#   - Python 3.11+ venv set up at backend/venv/
#   - Node.js 18+ with pnpm installed (or npm)
#   - pnpm install / npm install run in frontend/
#
# Press Ctrl+C to stop both servers.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
    echo ""
    echo "⏹  Shutting down..."
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null && echo "   Backend stopped"
    [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "   Frontend stopped"
    wait 2>/dev/null
    echo "✅ Done."
}

trap cleanup EXIT INT TERM

# ─── Backend ────────────────────────────────────────────────────────
echo "🚀 Starting backend..."
cd "$ROOT_DIR/backend"

# Activate venv if it exists; fall back to system Python
if [ -d "venv" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID  → http://localhost:8000"

# Give the backend a moment to start
sleep 2

# ─── Frontend ───────────────────────────────────────────────────────
echo "🚀 Starting frontend..."
cd "$ROOT_DIR/frontend"

if command -v pnpm &>/dev/null; then
    pnpm dev &
elif command -v npm &>/dev/null; then
    npm run dev &
else
    echo "❌ ERROR: Neither pnpm nor npm found. Install Node.js package manager."
    exit 1
fi

FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID  → http://localhost:5173"

echo ""
echo "═══════════════════════════════════════════════"
echo "  Backend:  http://localhost:8000"
echo "  Swagger:  http://localhost:8000/docs"
echo "  Frontend: http://localhost:5173"
echo "═══════════════════════════════════════════════"
echo "  Press Ctrl+C to stop all servers"
echo ""

# Wait for either process to exit
wait
