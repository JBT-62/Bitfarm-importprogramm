param(
    [Parameter(Mandatory=$true)][string]$TargetDb,
    [Parameter(Mandatory=$true)][string]$Backup
)
$ErrorActionPreference='Stop'
$targetJson = & python (Join-Path $PSScriptRoot 'migration_runtime.py') --target-info $TargetDb
if($LASTEXITCODE -ne 0){throw "Zieldatenbank $TargetDb ist nicht freigegeben"}
$target = $targetJson | ConvertFrom-Json
if(-not $Backup.StartsWith($target.backup_prefix)){throw "Passende Sicherung fuer $TargetDb erforderlich"}
$archive=Join-Path $env:TEMP 'kf_legacy_traceability_20260915.tar.gz'
if(Test-Path -LiteralPath $archive){Remove-Item -LiteralPath $archive -Force}
& tar -czf $archive -C (Join-Path $PSScriptRoot '..\odoo_addons') 'kf_legacy_migration'
if($LASTEXITCODE-ne 0){throw 'Addon-Archiv konnte nicht erstellt werden'}
$credentialFile=Join-Path $env:USERPROFILE '.codex\credentials\odoo-sudo.dpapi'
$storedSecret=(Get-Content -Raw -LiteralPath $credentialFile).Trim()
if($storedSecret.StartsWith('dpapi-v2:')){
    Add-Type -AssemblyName System.Security
    $protectedBytes=[Convert]::FromBase64String($storedSecret.Substring(9))
    $bytes=[System.Security.Cryptography.ProtectedData]::Unprotect($protectedBytes,$null,[System.Security.Cryptography.DataProtectionScope]::CurrentUser)
    $plain=[Text.Encoding]::UTF8.GetString($bytes)
}else{
    $secure=($storedSecret|ConvertTo-SecureString)
    $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try{$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
}
$dll=Get-ChildItem $env:USERPROFILE -Filter Renci.SshNet.dll -Recurse|Select-Object -First 1 -ExpandProperty FullName
[Reflection.Assembly]::LoadFrom($dll)|Out-Null
$auth=New-Object Renci.SshNet.PasswordAuthenticationMethod('kufadmin',$plain)
$ci=New-Object Renci.SshNet.ConnectionInfo('192.168.120.225','kufadmin',$auth)
$ssh=New-Object Renci.SshNet.SshClient($ci);$sftp=New-Object Renci.SshNet.SftpClient($ci)
$ssh.Connect();$sftp.Connect()
$stream=[IO.File]::OpenRead($archive)
try{$sftp.UploadFile($stream,'/tmp/kf_legacy_traceability_20260915.tar.gz',$true)}finally{$stream.Close()}
$payload=@"
set -e
test -s '$Backup/database.dump'
test -s '$Backup/filestore.tar.gz'
stamp=`$(date +%Y%m%d_%H%M%S)
install -d -o odoo -g odoo "/var/backups/odoo/addons_pre_legacy_traceability_`$stamp"
cp -a /opt/odoo/custom-addons/kf_legacy_migration "/var/backups/odoo/addons_pre_legacy_traceability_`$stamp/"
tar -xzf /tmp/kf_legacy_traceability_20260915.tar.gz -C /opt/odoo/custom-addons
chown -R odoo:odoo /opt/odoo/custom-addons/kf_legacy_migration
find /opt/odoo/custom-addons/kf_legacy_migration -type d -exec chmod 755 {} +
find /opt/odoo/custom-addons/kf_legacy_migration -type f -exec chmod 644 {} +
sudo -u odoo python3 -m compileall -q /opt/odoo/custom-addons/kf_legacy_migration
rm -f /tmp/kf_legacy_traceability_20260915.tar.gz
systemctl restart odoo
echo DEPLOY_OK
"@
$p64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload));$pw64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($plain))
$remote="printf '%s' '$pw64'|base64 -d|sudo -S -p '' bash -c `"`$(printf '%s' '$p64'|base64 -d)`""
$result=$ssh.RunCommand($remote);$sftp.Disconnect();$ssh.Disconnect();$plain=$null
if($result.ExitStatus-ne 0){throw "Deployment fehlgeschlagen: $($result.Error)"}
$result.Result.Trim()
