@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo   SlideAI PPT Generator - Local Version
echo ========================================
echo.
echo Starting server on http://127.0.0.1:2000
echo.
echo Press Ctrl+C to stop the server.
echo.

python\python.exe backend\app.py

pause
