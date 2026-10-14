@echo off
cd /d "%~dp0"
echo Updating...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -Update
