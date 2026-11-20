@echo off
setlocal
cd /d "%~dp0"
set "PATH=%~dp0;%PATH%"

set "APP0_DIR="
for %%D in (
    "%~dp0game_data"
    "%~dp0game_data\app0\uroot"
    "%~dp0CUSA12112\app0\uroot"
    "%~dp000_GAME_DUMP\CUSA12112\app0\uroot"
    "%~dp0..\00_GAME_DUMP\CUSA12112\app0\uroot"
    "%~dp0..\Persona 4\00_GAME_DUMP\CUSA12112\app0\uroot"
) do (
    if not defined APP0_DIR if exist "%%~D\data\ps4.cpk" set "APP0_DIR=%%~fD"
)

if not defined APP0_DIR (
    echo [ERROR] Game dump ^(data\ps4.cpk^) not found relative to %~dp0
    echo Letakkan dump di game_data\ atau jalankan "Persona 4 Dancing All Night.exe" untuk memilih folder game.
    pause
    exit /b 1
)

set "BB_CONFIG=%~dp0bbport.ini"
set "BB_DATA_DIR=%~dp0"
set "BB_GPU_USER_DIR=%~dp0user"
set "BB_GUEST_IN_PLACE=0"
set "BB_UFFD=0"
set "BB_COPY_GPU_BUFFERS=1"
set "BB_GPU_WRITE_TWINS=1"
set "BB_GPU_WRITE_TWINS_MAX=65536"
set "BB_PREUPLOAD=1"
set "BB_VBLANK_HZ=60"
set "BB_NEO=0"

title Persona 4: Dancing All Night PC Port
echo ===================================================
echo   Persona 4: Dancing All Night - PC Port
echo ===================================================
echo [INFO] Launching from %~dp0

:launch
"%~dp0p4dan_pc.exe" "%~dp0out\boot-linked.bin" --import-names "%~dp0out\import_names.txt" --content-profile "%~dp0out\content.bin" --patches "%~dp0out\patches.bin" --app0 "%APP0_DIR%" --user "%~dp0user" --timeout 0 %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="75" goto launch
if not "%RC%"=="0" (
    echo [ERROR] Game exited with code %RC%.
    pause
)
exit /b %RC%
