@echo off
setlocal
cd /d "%~dp0"
title Library shortcut

if /I "%~1"=="/?" goto :help
if /I "%~1"=="-?" goto :help
if /I "%~1"=="-Help" goto :help
if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help

echo.
echo  Create Library shortcuts on the Desktop and Start Menu.
echo  Safe to run again. Does not start Library.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create-shortcut.ps1" %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo  Could not create the shortcut. Try again, or pin Library.bat yourself.
    pause
    exit /b %ERR%
)
echo.
echo  Shortcut ready -- double-click Library on the Desktop.
pause
exit /b 0

:help
echo.
echo  CreateShortcut.bat  -- Desktop and Start Menu icon for Library
echo.
echo  Target is Library.bat in this folder. Icon is library.ico.
echo  Setup.bat also creates this shortcut. Re-run this file any time.
echo.
echo    CreateShortcut.bat         create or refresh the shortcuts
echo    CreateShortcut.bat -Help   this text
echo    CreateShortcut.bat -DryRun show paths only
echo.
exit /b 0
