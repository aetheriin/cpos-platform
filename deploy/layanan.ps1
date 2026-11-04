# Menjalankan CPOS + Analytics (+ Deteksi Plat bila ada) sebagai tugas terjadwal "CPOS Platform" (dipasang oleh pasang.ps1).
# Sama dengan jalankan.ps1, tetapi Python & library disimpan di C:\ProgramData\CPOS-Platform (bukan %LOCALAPPDATA% akun yang login),
# supaya akun SYSTEM yang menjalankan tugas saat Windows menyala dan admin yang memasang memakai folder yang sama.
# Log: C:\ProgramData\CPOS-Platform\cpos-platform\log (layanan.log = keluaran skrip ini).
$data = Join-Path $env:ProgramData 'CPOS-Platform'
$env:LOCALAPPDATA = $data
$env:PYTHONUNBUFFERED = '1'
$log = Join-Path $data 'cpos-platform\log'
New-Item -ItemType Directory -Force $log | Out-Null
Start-Transcript -Path (Join-Path $log 'layanan.log') -Append | Out-Null
Write-Host "Mulai $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') sebagai $env:USERNAME"
try {
    & (Join-Path (Split-Path $PSScriptRoot -Parent) 'jalankan.ps1')
}
finally {
    Write-Host "Berhenti $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Stop-Transcript | Out-Null
}
# CPOS berjalan terus selama tugas aktif; sampai di sini berarti berhenti / gagal -> kode 1 supaya Task Scheduler menyalakan ulang
exit 1
