@echo off
net session >nul 2>&1
if errorlevel 1 (
  echo Run as administrator orqali ishga tushiring.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0remove-agent.ps1"
pause
