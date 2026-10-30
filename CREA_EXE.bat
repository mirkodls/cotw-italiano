@echo off
chcp 65001 >nul
title Crea l'exe di CotW Italiano
cd /d "%~dp0"
echo ==========================================================
echo   CREA L'EXE DI COTW ITALIANO (per provarlo e per pubblicarlo)
echo ==========================================================
echo.
if not exist ".venv\Scripts\python.exe" goto novenv
set "PY=%~dp0.venv\Scripts\python.exe"

echo 1/3 Preparo PyInstaller (la prima volta serve internet)...
"%PY%" -m pip install --quiet --disable-pip-version-check "pyinstaller>=6.16"
if errorlevel 1 goto errore

echo 2/3 Creo l'exe (1-3 minuti)...
if exist "dist\CotW Italiano" rmdir /s /q "dist\CotW Italiano"
"%PY%" -m PyInstaller --noconfirm --clean --windowed --name "CotW Italiano" ^
  --icon "%~dp0risorse\icona.ico" --add-data "%~dp0risorse;risorse" ^
  --distpath "%~dp0dist" --workpath "%~dp0build\lavoro" --specpath "%~dp0build" ^
  "%~dp0CotW_Italiano.py"
if errorlevel 1 goto errore
if not exist "dist\CotW Italiano\CotW Italiano.exe" goto errore

echo 3/3 Creo lo zip da distribuire...
for /f "tokens=2 delims='" %%v in ('findstr /b "VERSIONE" "cotw\__init__.py"') do set "VER=%%v"
if exist "dist\CotW_Italiano_%VER%.zip" del "dist\CotW_Italiano_%VER%.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\CotW Italiano' -DestinationPath 'dist\CotW_Italiano_%VER%.zip'"
echo.
echo FATTO!
echo   Programma:  dist\CotW Italiano\CotW Italiano.exe   (doppio clic per provarlo)
echo   Da dare agli altri:  dist\CotW_Italiano_%VER%.zip
echo.
echo NOTA: la prima volta Windows puo' dire "PC protetto da Windows": e' normale per un exe nuovo
echo senza firma. Si apre con "Ulteriori informazioni" - "Esegui comunque".
start "" "%~dp0dist\CotW Italiano"
goto fine

:novenv
echo Prima avvia almeno una volta AVVIA_COTW_ITALIANO.bat (prepara Python).
goto fine

:errore
echo.
echo ERRORE durante la creazione dell'exe: manda a Claude uno screenshot di questa finestra.

:fine
echo.
pause
