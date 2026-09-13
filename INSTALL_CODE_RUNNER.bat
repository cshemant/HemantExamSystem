@echo off
setlocal
cd /d "%~dp0"
title Learn with Hemant - Code Runner Installation
echo This installs/checks Docker, Git, Node.js, Python, Piston, five languages, Java JDK and the Android APK builder.
echo Administrator approval and one Windows restart may be required on a new computer.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_code_runner_windows.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Installation and configuration completed successfully.
) else if "%RESULT%"=="10" (
  echo Restart Windows, then run this same file again.
) else (
  echo Setup stopped with error code %RESULT%. Read the message above.
)
pause
exit /b %RESULT%
