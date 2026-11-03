@echo off
echo ========================================================
echo Starting Sports Media Guard (Backend and Frontend)
echo ========================================================

echo Starting FastAPI Backend on http://localhost:8000 ...
start "SportsGuard Backend" cmd /k "cd backend && .\venv\Scripts\python.exe run_backend.py"

echo Starting Vite React Frontend on http://localhost:5173 ...
start "SportsGuard Frontend" cmd /k "cd frontend && npm run dev"

echo ========================================================
echo Both servers are launching in separate windows!
echo Backend API Docs: http://localhost:8000/docs
echo Frontend Web App: http://localhost:5173
echo ========================================================

