@echo off
echo Resetting Disruptopia...
if exist backend\disruptopia.db del /f backend\disruptopia.db
python backend\database.py
python backend\seed.py
echo Running tests...
python -m pytest -v