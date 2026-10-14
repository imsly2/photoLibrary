@echo off
cd /d "%~dp0"
echo Updating Library from main...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -Update
if errorlevel 1 (
    echo.
    echo  Update did not finish. Check the internet, then try Update.bat again.
    pause
    exit /b 1
)

