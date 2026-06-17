@echo off
REM ======================================================
REM  Executive Copilot — Start Backend & Frontend
REM  Usage:  start.bat
REM
REM  Starts both:
REM    - Backend  → http://localhost:8000  (FastAPI + uvicorn)
REM    - Frontend → http://localhost:5173  (Vite dev server)
REM ======================================================

setlocal enabledelayedexpansion
set "ROOT_DIR=%~dp0"

echo ========================================
echo  Executive Copilot - Starting Servers
echo ========================================
echo.

REM ─── Backend ──────────────────────────────────────────────
echo [1/2] Starting backend...
cd /d "%ROOT_DIR%backend"

REM Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo   Backend: http://localhost:8000
echo   Swagger: http://localhost:8000/docs
start "Executive-Copilot-Backend" cmd /c "uvicorn app.main:app --reload --port 8000 & pause"

REM Give the backend a moment to start
timeout /t 3 /nobreak >nul

REM ─── Frontend ─────────────────────────────────────────────
echo [2/2] Starting frontend...
cd /d "%ROOT_DIR%frontend"

if exist "node_modules\.package-lock.json" (
    echo   Using npm...
    start "Executive-Copilot-Frontend" cmd /c "npm run dev & pause"
) else if exist "node_modules" (
    echo   Using pnpm...
    start "Executive-Copilot-Frontend" cmd /c "pnpm dev & pause"
) else (
    echo !!! WARNING: node_modules not found.
    echo     Run: cd frontend ^&^& pnpm install
    echo.
    start "Executive-Copilot-Frontend" cmd /c "pnpm dev & pause"
)

echo.
echo ========================================
echo  Backend:  http://localhost:8000
echo  Swagger:  http://localhost:8000/docs
echo  Frontend: http://localhost:5173
echo ========================================
echo  Close the server windows to stop.
echo  Or press any key to exit (servers continue).
echo.
pause >nul

endlocal
