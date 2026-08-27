@echo off
setlocal
set "BACKEND_DIR=%~dp0backend"
set "FRONTEND_DIR=%~dp0frontend"

if not exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    echo ERROR: Backend virtual environment was not found.
    echo Expected: %BACKEND_DIR%\venv\Scripts\python.exe
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo ERROR: Frontend package.json was not found.
    echo Expected: %FRONTEND_DIR%\package.json
    pause
    exit /b 1
)
echo ========================================
echo   ZenAI — Starting both servers
echo ========================================
echo.

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
    echo Backend is already running on http://localhost:8000.
) else (
    echo Starting backend on http://localhost:8000...
    start "ZenAI Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && ""venv\Scripts\python.exe"" -m uvicorn app.main:app --reload --reload-exclude chroma_data --host 127.0.0.1 --port 8000"
)

netstat -ano | findstr /R /C:":3100 .*LISTENING" >nul
if not errorlevel 1 (
    echo Frontend is already running on http://localhost:3100.
) else (
    echo Starting frontend on http://localhost:3100...
    start "ZenAI Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev -- -p 3100"
)

echo.
echo ZenAI startup check complete.
pause
