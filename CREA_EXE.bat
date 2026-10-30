@echo off
chcp 65001 >nul
title Crea l'exe di CotW Italiano (prova sul PC)
cd /d "%~dp0"
echo ==========================================================
echo   CREA L'EXE DI COTW ITALIANO SUL TUO PC (solo per provarlo)
echo ==========================================================
echo  L'exe UFFICIALE da dare agli altri lo costruisce GitHub
echo  (Actions - "Crea exe del programma"): e' fatto con Nuitka e dai meno falsi allarmi agli antivirus.
echo  Questo qui usa PyInstaller: va bene per provare, non distribuirlo.
echo.
if not exist ".venv\Scripts\python.exe" goto novenv
set "PY=%~dp0.venv\Scripts\python.exe"
echo Preparo PyInstaller (la prima volta serve internet)...
"%PY%" -m pip install --quiet --disable-pip-version-check "pyinstaller>=6.16"
if errorlevel 1 goto errore
"%PY%" strumenti\costruisci_exe.py --metodo pyinstaller
if errorlevel 1 goto errore
echo.
echo FATTO:  dist\CotW Italiano\CotW Italiano.exe
start "" "%~dp0dist\CotW Italiano"
goto fine

:novenv
echo Prima avvia almeno una volta AVVIA_COTW_ITALIANO.bat (prepara Python).
goto fine

:errore
echo.
echo ERRORE: manda a Claude uno screenshot di questa finestra.

:fine
echo.
pause
