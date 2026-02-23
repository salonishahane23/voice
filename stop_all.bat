@echo off
echo Stopping all Interview Coach services...
taskkill /FI "WINDOWTITLE eq Backend API :8000" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Voice Service :8001" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq NLP Service :8002" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Facial Service :8003" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Frontend :5173" /F >nul 2>&1
echo All services stopped.
pause
