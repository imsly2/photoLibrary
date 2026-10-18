@echo off
setlocal
cd /d "%~dp0"
".\.venv\Scripts\python.exe" -m tests.perf.bench %*
set ERR=%ERRORLEVEL%
echo.
echo Exit code: %ERR%
pause
exit /b %ERR%
