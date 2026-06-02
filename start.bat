@echo off
title Amunty - Starting...
color 0B

echo.
echo  ╔══════════════════════════════════════╗
echo  ║         AMUNTY PC ASSISTANT          ║
echo  ╚══════════════════════════════════════╝
echo.

:: Start backend
echo [1/2] Starting backend (FastAPI on port 7000)...
cd /d "%~dp0backend"
start "Amunty Backend" cmd /k "color 0A & title Amunty Backend & python -m uvicorn amunty.main:app --host 0.0.0.0 --port 7000 --reload"

:: Wait for backend to be ready
echo      Waiting for backend...
timeout /t 3 /nobreak >nul

:: Start frontend
echo [2/2] Starting frontend (Vite on port 5173)...
cd /d "%~dp0frontend"
start "Amunty Frontend" cmd /k "color 0E & title Amunty Frontend & npm run dev"

:: Wait then open browser
echo.
echo  ✓ Both servers starting!
echo.
echo  Backend:  http://localhost:7000
echo  Frontend: http://localhost:5173
echo.
echo  To connect from mobile devices, navigate to your computer's local IP on port 5173.
echo  Example: http://192.168.x.x:5173
echo.
timeout /t 3 /nobreak >nul

:: Open in browser
start http://localhost:5173

echo  ✓ Opened in browser. You can close this window.
echo.
pause
