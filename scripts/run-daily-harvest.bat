@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-daily-harvest.ps1"
exit /b %ERRORLEVEL%
