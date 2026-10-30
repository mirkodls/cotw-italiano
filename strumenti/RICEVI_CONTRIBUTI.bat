@echo off
chcp 65001 >nul
title Ricevi contributi - CotW Italiano
cd /d "%~dp0"
set "PY=%~dp0..\..\audio italiano\Prova modelli\venv_voxcpm\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "LV=%~dp0..\..\audio italiano\lavoro_voci"

echo ==========================================================
echo   CONTRIBUTI DELLA COMMUNITY (battute doppiate dagli utenti)
echo ==========================================================
echo.
echo   1 = SCARICA i contributi nuovi (in mod italiano\contributi\da_ascoltare)
echo   2 = ACCETTA quelli rimasti in da_ascoltare e INSTALLALI nel gioco
echo       (prima ascoltali e CANCELLA quelli che non vanno bene)
echo   3 = PULISCI il postino (dopo aver pubblicato la versione con i contributi)
echo   0 = esci
echo.
set "SCELTA="
set /p "SCELTA=Scegli: "
if "%SCELTA%"=="1" goto scarica
if "%SCELTA%"=="2" goto accetta
if "%SCELTA%"=="3" goto pulisci
goto fine

:scarica
"%PY%" ricevi_contributi.py
start "" "%~dp0..\..\contributi\da_ascoltare"
goto fine

:accetta
echo Chiudi il gioco prima di continuare.
set "OK="
set /p "OK=Accetto TUTTO quello che c'e' in da_ascoltare? Scrivi SI: "
if /i not "%OK%"=="SI" goto fine
"%PY%" ricevi_contributi.py --accetta
if errorlevel 1 goto fine
echo.
echo Installo le voci nel gioco...
cd /d "%LV%"
"%PY%" installa_voci.py --lista _contributi_in_lavorazione.txt
echo.
echo Aggiorno i sottotitoli...
"%PY%" "..\..\Aggiornamento traduzione\strumento\applica_correzioni.py"
echo.
echo FATTO. Prova in gioco OFFLINE, poi 3_CREA_PACCHETTI_NEXUS.bat e PUBBLICA_AGGIORNAMENTO.bat
goto fine

:pulisci
"%PY%" ricevi_contributi.py --pulisci
goto fine

:fine
echo.
pause
