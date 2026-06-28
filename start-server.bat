@echo off
chcp 65001 >nul
title 血糖知识图谱 - 本地服务器
echo ========================================
echo   血糖知识图谱 · 本地开发服务器
echo ========================================
echo.
echo   Prompt 生成器: http://127.0.0.1:8766/prompt-generator.html
echo   口播稿工具:   http://127.0.0.1:8766/script-generator.html
echo.
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.

cd /d "%~dp0out"

:: 检查端口是否被占用
netstat -ano | findstr ":8766" >nul 2>&1
if %errorlevel%==0 (
    echo [!] 端口 8766 已被占用，尝试结束旧进程...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8766" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

:: 启动服务器
python -m http.server 8766 --bind 127.0.0.1

pause
