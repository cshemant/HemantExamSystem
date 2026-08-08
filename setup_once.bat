@echo off
cd /d "%~dp0"
title Learn with Hemant - First Time Setup
echo Installing offline/LAN requirements...
python -m pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
echo.
echo Setup finished. Internet is not required during exams.
pause
