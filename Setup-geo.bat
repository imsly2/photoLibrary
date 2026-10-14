@echo off
cd /d "%~dp0"
echo Fetching the offline cities pack into library-data\geo ...
python -m library setup-geo
if errorlevel 1 pause
