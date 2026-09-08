@echo off
setlocal
set "SCRIPT=%~dp0run.ps1"

echo NETA-LAB-004 test launcher starting PowerShell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo NETA-LAB-004 failed exit_code=%RC% 1>&2
)
exit /b %RC%
