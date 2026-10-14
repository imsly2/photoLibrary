@echo off
setlocal
cd /d "%~dp0"
title Library Setup

if /I "%~1"=="/?" goto :help
if /I "%~1"=="-?" goto :help
if /I "%~1"=="-Help" goto :help
if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help

echo.
echo  Library portable setup
echo  ----------------------
echo  This PC needs the internet for this first run.
echo  Setup once   -- this file  (Python, ffmpeg, local faces / objects / places)
echo  Shortcut     -- Desktop / Start Menu icon (also CreateShortcut.bat)
echo  Library      -- Library.bat every day
echo  Update       -- Update.bat or Update Library for new code  (git pull)
echo  No MSI. No GitHub account. Models stay in library-data. Safe to run again.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo  Setup did not finish. If it asked you to Update Library, do that, then run Setup.bat again.
    pause
    exit /b %ERR%
)
echo.
echo  Ready -- run Library.bat
echo  Or double-click the Library icon on the Desktop.
pause
exit /b 0

:help
echo.
echo  Setup.bat  -- one-time portable install on this Windows PC
echo.
echo  Setup once   -- this file  (Python 3.12+, ffmpeg, .venv, local AI models)
echo  Library      -- Library.bat every day
echo  Update       -- Update.bat or Update Library for new code  (git pull)
echo.
echo  First real run needs the internet for Python/ffmpeg (if missing)
echo  and the cities / objects / faces packs. After that, re-runs are local.
echo  Models stay under library-data\. No cloud APIs. No MSI.
echo  No GitHub account. No gh tool. Update can use git or a zip of main.
echo.
echo  Then use the Library Desktop icon, or Library.bat.
echo  Use Update.bat / Update Library for new code (pulls main, restarts if open).
echo.
echo    Setup.bat           run setup
echo    Setup.bat -Help     this text
echo    Setup.bat -DryRun   probe only; do not download, pip install, or winget
echo.
exit /b 0
