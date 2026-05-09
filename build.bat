@echo off
REM build.bat — Build HA-Minder on Windows
REM Usage: build.bat

setlocal

set SCRIPT_DIR=%~dp0
set VENV=%SCRIPT_DIR%.venv

echo =^> Using venv: %VENV%

if not exist "%VENV%" (
    echo =^> Creating virtual environment...
    python -m venv "%VENV%"
)

echo =^> Installing dependencies...
"%VENV%\Scripts\pip.exe" install -r "%SCRIPT_DIR%requirements.txt"

echo =^> Building HA-Minder.exe...
python "%SCRIPT_DIR%build.py"

endlocal
