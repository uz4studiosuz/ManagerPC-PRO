@echo off
net session >nul 2>&1
if errorlevel 1 (
  echo Ushbu faylni o'ng tugma bilan bosib Run as administrator ni tanlang.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-agent.ps1"
pause
