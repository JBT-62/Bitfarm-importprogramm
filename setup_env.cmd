@echo off
:: Legt .env im aktuellen Verzeichnis an (Odoo-Verbindungsdaten)
:: Ausfuehren aus dem Projektordner: setup_env.cmd

if exist .env (
    echo .env existiert bereits. Loeschen und neu erstellen? (J/N)
    set /p ANTWORT="> "
    if /i not "%ANTWORT%"=="J" goto :EOF
)

set ODOO_URL=http://192.168.120.225:8069
set ODOO_DB=erp-test-1
set ODOO_USER=admin

echo.
echo API-Key eingeben (aus Odoo Einstellungen > Technisch > API-Schluessel):
set /p ODOO_API_KEY="> "

if "%ODOO_API_KEY%"=="" (
    echo FEHLER: Kein API-Key eingegeben.
    exit /b 1
)

(
    echo ODOO_URL=%ODOO_URL%
    echo ODOO_DB=%ODOO_DB%
    echo ODOO_USER=%ODOO_USER%
    echo ODOO_API_KEY=%ODOO_API_KEY%
) > .env

echo.
echo [OK] .env erstellt:
type .env
