# Dijalankan di KOMPUTER DEVELOPER (bukan di server). Membuat deploy\paket\dashboard-analytics.zip berisi:
#   web\       hasil build frontend (termasuk web.config untuk IIS)
#   backend\   kode backend tanpa venv, tes, log, dan .env (rahasia; .env dibuat sendiri di server)
#   deploy\    skrip pasang, panduan, dan skrip SQL (SP yang dipasang lewat SSMS)
# Pakai:  powershell -ExecutionPolicy Bypass -File deploy\buat-paket.ps1
$ErrorActionPreference = 'Stop'
$akar = Split-Path -Parent $PSScriptRoot
$keluaran = Join-Path $PSScriptRoot 'paket'
$isi = Join-Path $keluaran 'dashboard-analytics'

Write-Host '1/3 Build frontend...'
Push-Location (Join-Path $akar 'frontend')
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'npm run build gagal.' }
} finally { Pop-Location }

Write-Host '2/3 Menyalin berkas...'
if (Test-Path $keluaran) { Remove-Item $keluaran -Recurse -Force }
New-Item -ItemType Directory -Force $isi | Out-Null
Copy-Item (Join-Path $akar 'frontend\dist') (Join-Path $isi 'web') -Recurse
$kecuali = @('venv', 'tests', 'log_aktivitas', '__pycache__', '.pytest_cache')
$berkasKecuali = @('.env', 'pengaturan.json', 'requirements-dev.txt')
Get-ChildItem (Join-Path $akar 'backend') | Where-Object { $kecuali -notcontains $_.Name -and $berkasKecuali -notcontains $_.Name } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $isi "backend\$($_.Name)") -Recurse -Force }
Get-ChildItem (Join-Path $isi 'backend') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force (Join-Path $isi 'deploy') | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'pasang-server.ps1'), (Join-Path $PSScriptRoot 'PANDUAN-IIS.md') (Join-Path $isi 'deploy')
Copy-Item (Join-Path $PSScriptRoot 'sql') (Join-Path $isi 'deploy\sql') -Recurse

Write-Host '3/3 Membuat zip...'
$zip = Join-Path $keluaran 'dashboard-analytics.zip'
Compress-Archive -Path $isi -DestinationPath $zip
Remove-Item $isi -Recurse -Force
Write-Host "Selesai: $zip"
Write-Host 'Salin zip ini ke server (lewat AnyDesk: File Transfer), lalu ikuti deploy\PANDUAN-IIS.md.'
