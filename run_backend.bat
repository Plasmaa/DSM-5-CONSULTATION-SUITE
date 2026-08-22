@echo off
title DSM-5 Consultation Suite Backend
echo ===================================================
echo   DSM-5 Consultation Suite - Backend Server Loader
echo ===================================================
echo.

:: Check if virtual environment exists
if not exist .venv (
    echo Error: .venv virtual environment folder not found!
    echo Please verify you have run setup before executing this script.
    echo.
    pause
    exit /b 1
)

:: Quick curl check on Ollama port
echo Checking local Ollama connection...
curl -s -I http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Local Ollama server does not seem to be running!
    echo Please ensure Ollama is active on port 11434 so RAG responses can generate.
    echo.
) else (
    echo [OK] Ollama server detected.
)

echo Starting FastAPI server via Uvicorn...
echo.
echo ===================================================
echo  - Local dashboard:  http://127.0.0.1:8000
echo  - Vercel dashboard: https://dsm-5-consultation-suite.vercel.app
echo ===================================================
echo.

:: Run FastAPI
.\.venv\Scripts\python -m uvicorn src.main:app --host 127.0.0.1 --port 8000

pause
