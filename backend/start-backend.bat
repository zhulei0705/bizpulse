@echo off
setlocal
cd /d %~dp0
if not exist .env copy .env.example .env >nul
if not exist data mkdir data
if not exist logs mkdir logs
python scripts\bootstrap.py
if errorlevel 1 exit /b 1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
