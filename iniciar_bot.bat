@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado. Consulte o README.md para configurar o bot.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -u bot.py
pause
