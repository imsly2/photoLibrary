@echo off
setlocal
cd /d "%~dp0"
echo Updating Library from main...
set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -AppFolder "%APPDIR%" -Update
if errorlevel 1 (
    echo.
    echo  Update did not finish. Check the internet, then try Update.bat again.
    pause
    exit /b 1
)

