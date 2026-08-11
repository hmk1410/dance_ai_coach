@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title WuJing-ZhiXin AI Dance Coach

if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv not found.
    echo Please install dependencies first, then run this script again.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo ================================================
echo   WuJing-ZhiXin - AI Dance Coach
echo   URL:  http://127.0.0.1:5000
echo   LAN:  http://<PC-IP>:5000
echo   Press Ctrl+C in this window to stop.
echo ================================================

start "" /b cmd /c "ping -n 4 127.0.0.1 >nul & start http://127.0.0.1:5000"

python run.py
pause
