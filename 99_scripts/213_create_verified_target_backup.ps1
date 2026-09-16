param(
    [Parameter(Mandatory=$true)][string]$TargetDb,
    [string]$Suffix = 'pre_import'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $PSScriptRoot 'migration_runtime.py'

if ($TargetDb -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unsicherer Datenbankname.' }
if ($Suffix -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unsicherer Sicherungszusatz.' }

$targetJson = & python $runtime --target-info $TargetDb
if ($LASTEXITCODE -ne 0) { throw "Zieldatenbank $TargetDb ist nicht freigegeben." }
$target = $targetJson | ConvertFrom-Json

$credentialFile = Join-Path $env:USERPROFILE '.codex\credentials\odoo-sudo.dpapi'
if (-not (Test-Path -LiteralPath $credentialFile)) { throw 'Server-Zugangskapsel fehlt.' }
$storedSecret = (Get-Content -Raw -LiteralPath $credentialFile).Trim()
if ($storedSecret.StartsWith('dpapi-v2:')) {
    Add-Type -AssemblyName System.Security
    $protectedBytes = [Convert]::FromBase64String($storedSecret.Substring(9))
    $bytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
        $protectedBytes, $null,
        [System.Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    $plain = [Text.Encoding]::UTF8.GetString($bytes)
} else {
    $secure = ($storedSecret | ConvertTo-SecureString)
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

$dll = Get-ChildItem $env:USERPROFILE -Filter Renci.SshNet.dll -Recurse |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $dll) { throw 'Renci.SshNet.dll fehlt.' }
[Reflection.Assembly]::LoadFrom($dll) | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = "$($target.backup_prefix)$($stamp)_$Suffix"
$probe = "kf_restore_probe_$($stamp)"
$payload = @"
set -euo pipefail
db='$TargetDb'
backup='$backup'
probe='$probe'
probe_dump="/tmp/`$probe.dump"
case "`$db" in *[!A-Za-z0-9_-]*) exit 91;; esac
case "`$probe" in kf_restore_probe_[0-9]*) ;; *) exit 92;; esac
cleanup() {
  sudo -u postgres dropdb --if-exists "`$probe" >/dev/null 2>&1 || true
  rm -f "`$probe_dump"
}
trap cleanup EXIT
mkdir -p "`$backup"
chmod 750 "`$backup"
sudo -u postgres pg_dump -Fc -d "`$db" > "`$backup/database.dump"
tar -C /opt/odoo/.local/share/Odoo/filestore -czf "`$backup/filestore.tar.gz" "`$db"
test -s "`$backup/database.dump"
test -s "`$backup/filestore.tar.gz"
pg_restore --list "`$backup/database.dump" >/dev/null
tar -tzf "`$backup/filestore.tar.gz" "`$db/" >/dev/null
sudo -u postgres createdb "`$probe"
install -o postgres -g postgres -m 600 "`$backup/database.dump" "`$probe_dump"
sudo -u postgres pg_restore --no-owner --no-privileges -d "`$probe" "`$probe_dump"
probe_modules=`$(sudo -u postgres psql -X -A -t -d "`$probe" -c 'SELECT count(*) FROM ir_module_module;')
test "`$probe_modules" -gt 0
stat -c '%n|%s' "`$backup/database.dump" "`$backup/filestore.tar.gz"
printf 'RESTORE_PROBE_MODULES=%s\n' "`$probe_modules"
printf 'BACKUP=%s\n' "`$backup"
"@

$auth = New-Object Renci.SshNet.PasswordAuthenticationMethod('kufadmin', $plain)
$connection = New-Object Renci.SshNet.ConnectionInfo('192.168.120.225', 'kufadmin', $auth)
$ssh = New-Object Renci.SshNet.SshClient($connection)
$ssh.Connect()
try {
    $payload64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
    $password64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($plain))
    $remote = "script=`$(mktemp); printf '%s' '$payload64' | base64 -d > `"`$script`"; printf '%s' '$password64' | base64 -d | sudo -S -p '' bash `"`$script`"; rc=`$?; rm -f `"`$script`"; exit `$rc"
    $result = $ssh.RunCommand($remote)
    if ($result.ExitStatus -ne 0) { throw "Sicherung fehlgeschlagen: $($result.Error)" }
    $result.Result.Trim()
}
finally {
    $ssh.Disconnect()
    $plain = $null
}
