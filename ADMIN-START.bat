@echo off
cd /d "%~dp0"
if exist "%~dp0ManagerPC-Admin-4.exe" (
  "%~dp0ManagerPC-Admin-4.exe"
  pause
  exit /b
)
if exist "%~dp0ManagerPC-Admin-v3.exe" (
  "%~dp0ManagerPC-Admin-v3.exe"
  pause
  exit /b
)
if exist "%~dp0ManagerPC-Admin-v2.exe" (
  "%~dp0ManagerPC-Admin-v2.exe"
  pause
  exit /b
)
if exist "%~dp0ManagerPC-Admin.exe" (
  "%~dp0ManagerPC-Admin.exe"
  pause
  exit /b
)
python --version >nul 2>&1
if errorlevel 1 (
  echo Python 3 topilmadi. README.md dagi o'rnatish yo'riqnomasini o'qing.
  pause
  exit /b 1
)
python server.py
pause
