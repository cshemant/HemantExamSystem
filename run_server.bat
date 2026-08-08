@echo off
cd /d "%~dp0"
title Learn with Hemant - Offline Exam Server
if not exist .env (
  copy .env.example .env >nul
)
echo.
echo Starting Learn with Hemant Exam System in OFFLINE/LAN mode...
echo.
python app.py
pause
