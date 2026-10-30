@echo off
chcp 65001 >nul
title Pubblica aggiornamento - CotW Italiano
cd /d "%~dp0"
set "PY=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PY%" goto nopy

echo ==========================================================
echo   PUBBLICA UNA NUOVA VERSIONE DELLA MOD SU GITHUB
echo ==========================================================
echo.
echo  Prende i file da  Desktop\mod italiano\MOD
echo  (prima lancia 3_CREA_PACCHETTI_NEXUS.bat se hai cambiato qualcosa)
echo.
echo   1 = PROVA (prepara tutto ma NON carica niente)
echo   2 = PUBBLICA DAVVERO (serve github_token.txt)
echo   0 = esci
echo.
set "SCELTA="
set /p "SCELTA=Scegli 1, 2 o 0: "
if "%SCELTA%"=="1" goto prova
if "%SCELTA%"=="2" goto vero
goto fine

:prova
"%PY%" pubblica.py --prova
goto fine

:vero
echo.
echo Scrivi le novita' separate da ;  (es: Corrette 3 battute di Salvador; Nuova mappa)
set "NOV="
set /p "NOV=Novita': "
echo.
echo Sto per caricare su GitHub. Tutti gli utenti vedranno l'aggiornamento.
set "OK="
set /p "OK=Scrivi SI per confermare: "
if /i not "%OK%"=="SI" goto fine
"%PY%" pubblica.py --novita "%NOV%"
goto fine

:nopy
echo Prima avvia almeno una volta AVVIA_COTW_ITALIANO.bat (prepara Python).

:fine
echo.
pause
