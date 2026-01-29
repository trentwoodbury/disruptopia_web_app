@echo off
echo Starting Disruptopia...

:: Check if something is running on port 8000 and kill it
echo Cleaning up existing server processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    if not "%%a"=="" (
        echo Killing process ID: %%a
        taskkill /F /PID %%a 2>nul
    )
)

call .venv\Scripts\activate.bat
echo Opening browser...
start "" "frontend\index.html"
echo Starting FastAPI server...
uvicorn backend.main:app --host 127.0.0.1 --port 8000