@echo off
title CotW Italiano
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" goto :avvia
echo Prima volta: preparo il programma (serve internet, 1-2 minuti)...
py -3 -m venv .venv >nul 2>nul
if exist ".venv\Scripts\python.exe" goto :pacchetti
python -m venv .venv >nul 2>nul
if exist ".venv\Scripts\python.exe" goto :pacchetti
"..\audio italiano\Prova modelli\venv_voxcpm\Scripts\python.exe" -m venv .venv
if exist ".venv\Scripts\python.exe" goto :pacchetti
echo ERRORE: non trovo Python. Installalo da python.org (spunta "Add python.exe to PATH") e riprova.
pause
exit /b
:pacchetti
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check PySide6==6.10.1
if errorlevel 1 goto :errpip
:avvia
start "" ".venv\Scripts\pythonw.exe" "%~dp0CotW_Italiano.py"
exit /b
:errpip
echo ERRORE durante l'installazione dei componenti. Controlla la connessione e riprova.
rmdir /s /q ".venv"
pause
