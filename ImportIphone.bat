@echo off
setlocal
cd /d "%~dp0"
set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -AppFolder "%APPDIR%" -Attach -Page import-iphone
if errorlevel 1 pause
