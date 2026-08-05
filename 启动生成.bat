@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo   SlideAI 本地版 - PPT生成工具
echo   访问 http://127.0.0.1:5000
echo ========================================
echo.

start http://127.0.0.1:5000
python\python.exe web_app.py

pause
