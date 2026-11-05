# Memasang HTTPS di server lewat Caddy. Jalankan sebagai Administrator di server, dari folder deploy:
#   powershell -ExecutionPolicy Bypass -File pasang_https.ps1 -IpServer 172.20.111.4 -Akar C:\CPOS-Platform -Port 8080
# Syarat: caddy.exe (Windows amd64, dari https://caddyserver.com/download) sudah ada di folder ini.
param(
    [Parameter(Mandatory)][string]$IpServer,
    [Parameter(Mandatory)][string]$Akar,
    [int]$Port = 8080
)
$ErrorActionPreference = 'Stop'
$caddy = Join-Path $PSScriptRoot 'caddy.exe'
if (-not (Test-Path $caddy)) { throw "caddy.exe belum ada di $PSScriptRoot" }
$envCpos = Join-Path $Akar 'CPOS\.env'
if (-not (Test-Path $envCpos)) { throw "Tidak menemukan $envCpos" }

function Atur($berkas, $kunci, $nilai) {
    $t = [IO.File]::ReadAllText($berkas)
    if ($t -match "(?m)^$kunci=") { $t = $t -replace "(?m)^$kunci=.*", "$kunci=$nilai" } else { $t = $t.TrimEnd() + "`r`n$kunci=$nilai`r`n" }
    [IO.File]::WriteAllText($berkas, $t, (New-Object Text.UTF8Encoding $false))
}

Copy-Item $envCpos "$envCpos.sebelum-https" -Force
Atur $envCpos 'BEHIND_PROXY' '1'
Atur $envCpos 'COOKIE_SECURE' '1'
Atur $envCpos 'HOST' '127.0.0.1'

$aktif = Join-Path $PSScriptRoot 'Caddyfile.aktif'
$isi = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'Caddyfile')).Replace('@IP@', $IpServer).Replace('@AKAR@', ($Akar -replace '\\', '/')).Replace('@PORT@', "$Port")
[IO.File]::WriteAllText($aktif, $isi, (New-Object Text.UTF8Encoding $false))
& $caddy validate --config $aktif --adapter caddyfile
if ($LASTEXITCODE) { throw 'Caddyfile tidak valid' }

New-NetFirewallRule -DisplayName 'CPOS HTTPS' -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow -ErrorAction SilentlyContinue | Out-Null
$aksi = New-ScheduledTaskAction -Execute $caddy -Argument "run --config `"$aktif`" --adapter caddyfile" -WorkingDirectory $PSScriptRoot
$pemicu = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName 'CPOS Caddy HTTPS' -Action $aksi -Trigger $pemicu -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName 'CPOS Caddy HTTPS'

Write-Host "Selesai. Restart CPOS dan Analytics, lalu buka https://$IpServer/"
Write-Host 'Sertifikat akar untuk dipasang di PC pengguna (Trusted Root Certification Authorities):'
Write-Host '  C:\Windows\System32\config\systemprofile\AppData\Roaming\Caddy\pki\authorities\local\root.crt'
Write-Host "Batal: kembalikan $envCpos.sebelum-https lalu hapus task 'CPOS Caddy HTTPS'."
