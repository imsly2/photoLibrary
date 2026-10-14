@echo off
setlocal
cd /d "%~dp0"
title Library Pack Deploy

if /I "%~1"=="/?" goto :help
if /I "%~1"=="-?" goto :help
if /I "%~1"=="-Help" goto :help
if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help

echo.
echo  Library deploy zip
echo  ------------------
echo  Writes dist\photoLibrary-deploy.zip (overwrites that file).
echo  App only -- no .venv, library-data, docs, tests, or .git.
echo  Next: copy the zip, extract it, then Setup.bat.
echo.

set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pack-deploy.ps1" -AppFolder "%APPDIR%" %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo  Pack did not finish.
    echo  Need Python 3 in this folder, or run PackDeploy.bat from the Library folder.
    pause
    exit /b %ERR%
)
echo.
echo  Copy the zip, extract it, then run Setup.bat on that PC.
pause
exit /b 0

:help
echo.
echo  PackDeploy.bat  -- write a lean zip for USB / family PCs
echo.
echo  Writes dist\photoLibrary-deploy.zip (overwrites that file).
echo  The zip is the app only: Setup, Library, Update, and library code.
echo  It does not include .venv, library-data, docs, tests, or .git.
echo.
echo  Copy the zip, extract it, then run Setup.bat on the other PC.
echo  Safe to run again. No MSI. Does not start Library.
echo.
echo    PackDeploy.bat           write the zip
echo    PackDeploy.bat -Help     this text
echo    PackDeploy.bat -DryRun   list includes and excludes; do not write the zip
echo.
exit /b 0
