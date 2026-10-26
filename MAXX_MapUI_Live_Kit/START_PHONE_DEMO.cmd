@echo off
cd /d "%~dp0"
echo Connect phones to the same trusted Wi-Fi, then use the laptop IPv4 address.
ipconfig
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py --host 0.0.0.0
) else (
  python server.py --host 0.0.0.0
)
pause
