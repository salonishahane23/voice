@echo off
title AI Interview Coach - Service Launcher
echo ========================================
echo   AI Interview Coach - Starting All Services
echo ========================================
echo.

:: Start Backend API (port 8000)
echo [1/5] Starting Backend API on port 8000...
start "Backend API :8000" cmd /k "cd /d c:\Users\OWNER\Desktop\voice\backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3 /nobreak >nul

:: Start Voice Analysis Service (port 8001)
echo [2/5] Starting Voice Analysis on port 8001...
start "Voice Service :8001" cmd /k "cd /d c:\Users\OWNER\Desktop\voice\ai_services\voice_analysis && python -m uvicorn service:app --host 127.0.0.1 --port 8001 --reload"
timeout /t 2 /nobreak >nul

:: Start NLP Analysis Service (port 8002)
echo [3/5] Starting NLP Analysis on port 8002...
start "NLP Service :8002" cmd /k "cd /d c:\Users\OWNER\Desktop\voice\ai_services\nlp_analysis && python -m uvicorn service:app --host 127.0.0.1 --port 8002 --reload"
timeout /t 2 /nobreak >nul

:: Start Facial Analysis Service (port 8003)
echo [4/5] Starting Facial Analysis on port 8003...
start "Facial Service :8003" cmd /k "cd /d c:\Users\OWNER\Desktop\voice\ai_services\facial_analysis && python -m uvicorn service:app --host 127.0.0.1 --port 8003 --reload"
timeout /t 2 /nobreak >nul

:: Start Frontend Dev Server (port 5173)
echo [5/5] Starting React Frontend on port 5173...
start "Frontend :5173" cmd /k "cd /d c:\Users\OWNER\Desktop\voice\frontend && npx vite --host 127.0.0.1 --port 5173"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   All services started!
echo ========================================
echo.
echo   Frontend:  http://127.0.0.1:5173
echo   Backend:   http://127.0.0.1:8000/docs
echo   Voice:     http://127.0.0.1:8001
echo   NLP:       http://127.0.0.1:8002
echo   Facial:    http://127.0.0.1:8003
echo.
echo   Close this window to keep services running,
echo   or press any key to stop all services.
echo.
pause

:: Kill all services
taskkill /FI "WINDOWTITLE eq Backend API :8000" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Voice Service :8001" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq NLP Service :8002" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Facial Service :8003" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Frontend :5173" /F >nul 2>&1
echo All services stopped.
