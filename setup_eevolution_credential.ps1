[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$credentialDirectory = Join-Path $env:USERPROFILE '.codex\credentials'
$credentialFile = Join-Path $credentialDirectory 'eevolution-sql-password.dpapi'

Write-Host 'eEvolution SQL – sichere lokale Einrichtung'
Write-Host 'Benutzer: excel_kuf_readonly'
Write-Host 'Das Kennwort wird bei der Eingabe nicht angezeigt.'
$securePassword = Read-Host 'SQL-Kennwort' -AsSecureString

$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $env:EV_SERVER = '192.168.120.234,1433'
    $env:EV_DATABASE = 'KuF'
    $env:EV_DRIVER = 'ODBC Driver 18 for SQL Server'
    $env:EV_TRUSTED = 'no'
    $env:EV_USER = 'excel_kuf_readonly'
    $env:EV_PASSWORD = $plainPassword

    @'
import os
import pyodbc

connection_string = (
    f"DRIVER={{{os.environ['EV_DRIVER']}}};"
    f"SERVER={os.environ['EV_SERVER']};"
    f"DATABASE={os.environ['EV_DATABASE']};"
    f"UID={os.environ['EV_USER']};"
    f"PWD={os.environ['EV_PASSWORD']};"
    "Encrypt=yes;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;"
)
with pyodbc.connect(connection_string, readonly=True, timeout=10) as connection:
    row = connection.cursor().execute(
        "SELECT DB_NAME(), SUSER_SNAME(), COUNT(*) FROM sys.tables"
    ).fetchone()
    print(f"SQL_TEST_OK Datenbank={row[0]} Benutzer={row[1]} Tabellen={row[2]}")
'@ | python -
    if ($LASTEXITCODE -ne 0) {
        throw 'Die SQL-Anmeldung wurde abgelehnt. Es wurde nichts gespeichert.'
    }

    New-Item -ItemType Directory -Path $credentialDirectory -Force | Out-Null
    $securePassword | ConvertFrom-SecureString | Set-Content -LiteralPath $credentialFile -Encoding ASCII
    Write-Host "Zugang erfolgreich geprüft und Windows-benutzergebunden verschlüsselt gespeichert."
    Write-Host "Datei: $credentialFile"
}
finally {
    Remove-Item Env:EV_PASSWORD -ErrorAction SilentlyContinue
    $plainPassword = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}
