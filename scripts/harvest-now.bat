@echo off
REM 每日选题采集 — 手动立即执行入口
REM 双击此文件即可立即运行采集日报
echo [%date% %time%] 开始执行每日选题采集...
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run-daily-harvest.ps1"
if %ERRORLEVEL% neq 0 (
    echo [%date% %time%] 采集失败，退出码: %ERRORLEVEL%
    pause
) else (
    echo [%date% %time%] 采集完成!
    pause
)
