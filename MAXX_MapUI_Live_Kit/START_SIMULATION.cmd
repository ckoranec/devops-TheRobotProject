@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py --mode simulation --port 8004
) else (
  python server.py --mode simulation --port 8004
)
pause
