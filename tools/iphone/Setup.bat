@echo off
setlocal
cd /d "%~dp0"
title iPhone photos setup

if /I "%~1"=="/?" goto :help
if /I "%~1"=="-?" goto :help
if /I "%~1"=="-Help" goto :help
if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help

echo.
echo  iPhone photos setup
echo  -------------------
echo  This PC needs the internet the first time.
echo  Setup once   -- this file  (Python, .NET 10, Apple USB driver)
echo  Window       -- Launch-Window.ps1
echo  Does not copy photos. Safe to run again.
echo.

set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -AppFolder "%APPDIR%" %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo  Setup did not finish. Do not open the window yet.
    pause
    exit /b %ERR%
)
echo.
echo  Ready -- run Launch-Window.ps1
if /I "%~1"=="-DryRun" exit /b 0
pause
exit /b 0

:help
echo.
echo  Setup.bat  -- one-time install on this Windows PC
echo.
echo  Setup once   -- Python 3.12+ (window), .NET 10 runtime (phone helper),
echo                  Apple Devices if no USB driver is installed
echo  Window       -- Launch-Window.ps1
echo.
echo  Does not copy photos. No pip packages for the window.
echo.
echo    Setup.bat           run setup
echo    Setup.bat -Help     this text
echo    Setup.bat -DryRun   probe only; do not winget or build
echo.
exit /b 0
