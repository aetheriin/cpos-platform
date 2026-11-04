# Membuat paket deploy (zip) CPOS Platform untuk dipasang di PC lain. Dipanggil oleh deploy\buat_paket.bat.
# Isi: semua file repo yang tidak di-.gitignore (CPOS + RekapIn, Analytics, Deteksi, skrip jalankan & deploy), tampilan Analytics
# yang baru dibangun (Analytics\frontend\dist), dan file .env yang sekarang (-TanpaEnv: tidak ikut, isi sendiri di PC tujuan).
# Tidak ikut: venv, node_modules, log, upload, cache laporan, sumber frontend Analytics (yang dipakai hanya dist).
# Hasil: deploy\paket\CPOS-Platform-<tanggal-jam>.zip. Pasang di PC tujuan: ekstrak ke mis. C:\CPOS-Platform, lalu
# klik kanan deploy\pasang.bat > Run as administrator (lihat PASANG.txt di dalam zip).
# -Port 8080: port CPOS di .env dalam paket (PORT dan CPOS_URL), dan Deteksi Plat di port internal -PortDeteksi yang hanya bisa
# dihubungi dari PC itu (CPOS meneruskan videonya). .env di folder ini tidak berubah.
param([switch]$TanpaEnv, [switch]$TanpaBangun, [int]$Port = 0, [int]$PortDeteksi = 8002)
$ErrorActionPreference = 'Stop'
$akar = Split-Path $PSScriptRoot -Parent
$kerja = Join-Path $env:LOCALAPPDATA 'cpos-platform'
$nama = "CPOS-Platform-$(Get-Date -Format 'yyyyMMdd-HHmm')"
$isi = Join-Path $kerja "paket\$nama"
$keluar = Join-Path $PSScriptRoot 'paket'

try {
    if (-not $TanpaBangun) {
        Write-Host '== 1. Membangun tampilan Analytics'
        $bangun = Join-Path $kerja 'bangun-frontend'
        robocopy (Join-Path $akar 'Analytics\frontend') $bangun /E /XD node_modules dist /NFL /NDL /NJH /NJS /NP | Out-Null
        Push-Location $bangun
        try {
            & npm install --no-audit --no-fund --loglevel=error
            if ($LASTEXITCODE -ne 0) { throw 'npm install gagal' }
            & npm run build
            if ($LASTEXITCODE -ne 0) { throw 'npm run build gagal' }
        } finally { Pop-Location }
        robocopy (Join-Path $bangun 'dist') (Join-Path $akar 'Analytics\frontend\dist') /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    }
    if (-not (Test-Path (Join-Path $akar 'Analytics\frontend\dist\index.html'))) { throw 'Analytics\frontend\dist belum ada. Jalankan tanpa -TanpaBangun.' }

    Write-Host '== 2. Menyalin file'
    Push-Location $akar
    try {
        $daftar = & git -c safe.directory=* ls-files --cached --others --exclude-standard
        if ($LASTEXITCODE -ne 0 -or -not $daftar) { throw 'git ls-files gagal. Pastikan Git terpasang dan folder ini repo git.' }
    } finally { Pop-Location }
    # Sumber frontend tidak perlu di PC tujuan (yang dilayani hanya dist)
    $daftar = $daftar | Where-Object { $_ -notlike 'Analytics/frontend/*' -or $_ -like 'Analytics/frontend/public/*' } |
                        Where-Object { $_ -notlike 'deploy/paket/*' -and $_ -notlike '*/log_aktivitas/*' }
    if (Test-Path $isi) { Remove-Item $isi -Recurse -Force }
    foreach ($f in $daftar) {
        $sumber = Join-Path $akar $f
        if (-not (Test-Path $sumber -PathType Leaf)) { continue }        # file terhapus yang belum di-commit
        $tujuan = Join-Path $isi $f
        New-Item -ItemType Directory -Force (Split-Path $tujuan) | Out-Null
        Copy-Item $sumber $tujuan
    }
    robocopy (Join-Path $akar 'Analytics\frontend\dist') (Join-Path $isi 'Analytics\frontend\dist') /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    if (-not $TanpaEnv) {
        foreach ($f in 'CPOS\.env', 'Analytics\backend\.env', 'Deteksi\.env') {
            if (Test-Path (Join-Path $akar $f)) { Copy-Item (Join-Path $akar $f) (Join-Path $isi $f) }
        }
    }
    if ($Port -and -not $TanpaEnv) {
        $f = Join-Path $isi 'CPOS\.env'
        [IO.File]::WriteAllText($f, ([IO.File]::ReadAllText($f) -replace '(?m)^PORT=\d+', "PORT=$Port" -replace '(?m)^URL_DETEKTOR=.*$', "URL_DETEKTOR=http://127.0.0.1:$PortDeteksi"))
        $f = Join-Path $isi 'Deteksi\.env'
        if (Test-Path $f) { [IO.File]::AppendAllText($f, "`r`nPORT_WEB=$PortDeteksi`r`nHOST_WEB=127.0.0.1`r`n") }
        $f = Join-Path $isi 'Analytics\backend\.env'
        [IO.File]::WriteAllText($f, ([IO.File]::ReadAllText($f) -replace '(?m)^(CPOS_URL=http://127\.0\.0\.1:)\d+', "`${1}$Port"))
    }
    Copy-Item (Join-Path $PSScriptRoot 'PASANG.txt') (Join-Path $isi 'PASANG.txt')

    Write-Host '== 3. Membuat zip'
    New-Item -ItemType Directory -Force $keluar | Out-Null
    $zip = Join-Path $keluar "$nama.zip"
    Compress-Archive -Path (Join-Path $isi '*') -DestinationPath $zip -CompressionLevel Optimal
    Remove-Item $isi -Recurse -Force
    $mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Host ''
    Write-Host "Selesai: $zip ($mb MB, $($daftar.Count) file + dist)" -ForegroundColor Green
    if (-not $TanpaEnv) { Write-Warning 'Zip berisi file .env (password database). Simpan dan kirim hanya lewat jalur internal.' }
}
catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
