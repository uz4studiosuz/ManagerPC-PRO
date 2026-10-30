@echo off
net session >nul 2>&1
if errorlevel 1 (
  echo Run as administrator orqali ishga tushiring.
  pause
  exit /b 1
)
netsh advfirewall firewall add rule name="ManagerPC 4 TLS" dir=in action=allow protocol=TCP localport=8766 profile=private remoteip=localsubnet
pause
