@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 pause
exit /b %EXIT_CODE%
