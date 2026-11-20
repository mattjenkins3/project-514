@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3 start_demo.py
goto done
:usepython
python start_demo.py
:done
if errorlevel 1 pause
