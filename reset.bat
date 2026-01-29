@echo off
echo Resetting Disruptopia...
call .venv\Scripts\activate.bat
if exist backend\disruptopia.db del /f backend\disruptopia.db
python -m backend.database
python -m backend.seed
echo Running tests...
python -m pytest -v