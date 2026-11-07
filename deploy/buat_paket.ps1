# Membuat paket deploy (zip) CPOS Platform untuk dipasang di PC lain. Dipanggil oleh deploy\buat_paket.bat.
# Isi: semua file repo yang tidak di-.gitignore (CPOS + RekapIn, Analytics, Deteksi, skrip jalankan & deploy), tampilan Analytics
# yang baru dibangun (Analytics\frontend\dist), dan file .env yang sekarang (-TanpaEnv: tidak ikut, isi sendiri di PC tujuan).
# Tidak ikut: venv, node_modules, log, upload, cache laporan, sumber frontend Analytics (yang dipakai hanya dist).
# Hasil: deploy\paket\CPOS-Platform-<tanggal-jam>.zip. Pasang di PC tujuan: ekstrak ke mis. C:\CPOS-Platform, lalu
# klik kanan deploy\pasang.bat > Run as administrator (lihat PASANG.txt di dalam zip).
# -Port 8080: port CPOS di .env dalam paket (PORT dan CPOS_URL), dan Deteksi Plat di port internal -PortDeteksi yang hanya bisa
# dihubungi dari PC itu (CPOS meneruskan videonya). .env di folder ini tidak berubah.
# Paket perubahan: setiap paket mencatat sidik file di deploy\paket\terakhir.json. Bila catatan itu ada, paket berikutnya hanya berisi
# file yang berbeda dari paket sebelumnya, ditambah HAPUS.txt untuk file yang sudah tidak ada. Paket perubahan dipasang berurutan.
# -Penuh: paket lengkap walau catatan ada. -Dasar <zip>: hanya menyusun ulang catatan dari zip lengkap yang terpasang di server.
param([switch]$TanpaEnv, [switch]$TanpaBangun, [int]$Port = 0, [int]$PortDeteksi = 8002, [switch]$Penuh, [string]$Dasar)
$ErrorActionPreference = 'Stop'

function Sidik-Folder($folder) {
    $akarFolder = (Resolve-Path $folder).Path.TrimEnd('\')
    $hasil = @{}
    Get-ChildItem $folder -Recurse -File -Force | ForEach-Object {
        $hasil[$_.FullName.Substring($akarFolder.Length + 1).Replace('\', '/')] = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    }
    return $hasil
}

function Simpan-Catatan($sidik, $berkas) {
    New-Item -ItemType Directory -Force (Split-Path $berkas) | Out-Null
    [IO.File]::WriteAllText($berkas, ($sidik | ConvertTo-Json -Compress))
}

$akar = Split-Path $PSScriptRoot -Parent
$kerja = Join-Path $env:LOCALAPPDATA 'cpos-platform'
$nama = "CPOS-Platform-$(Get-Date -Format 'yyyyMMdd-HHmm')"
$isi = Join-Path $kerja "paket\$nama"
$keluar = Join-Path $PSScriptRoot 'paket'
$catatan = Join-Path $keluar 'terakhir.json'

try {
    if ($Dasar) {
        $sementara = Join-Path $kerja "paket\dasar-$(Get-Date -Format 'yyyyMMddHHmmss')"
        Expand-Archive -Path $Dasar -DestinationPath $sementara
        try { $sidikDasar = Sidik-Folder $sementara } finally { Remove-Item $sementara -Recurse -Force }
        Simpan-Catatan $sidikDasar $catatan
        Write-Host "Catatan disusun dari $Dasar ($($sidikDasar.Count) file)." -ForegroundColor Green
        exit 0
    }
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
                        Where-Object { $_ -notlike 'deploy/paket/*' -and $_ -notlike '*/log_aktivitas/*' -and $_ -notlike 'Deteksi/foto_bukti/*' }
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
        [IO.File]::WriteAllText($f, ([IO.File]::ReadAllText($f) -replace '(?m)^PORT=\d+', "PORT=$Port" -replace '(?m)^URL_DETEKTOR=.*$', "URL_DETEKTOR=http://127.0.0.1:$PortDeteksi" -replace '(?m)^DETEKTOR_PORT=.*$', "DETEKTOR_PORT=$PortDeteksi"))
        $f = Join-Path $isi 'Deteksi\.env'
        if (Test-Path $f) { [IO.File]::AppendAllText($f, "`r`nPORT_WEB=$PortDeteksi`r`nHOST_WEB=127.0.0.1`r`n") }
        $f = Join-Path $isi 'Analytics\backend\.env'
        [IO.File]::WriteAllText($f, ([IO.File]::ReadAllText($f) -replace '(?m)^(CPOS_URL=http://127\.0\.0\.1:)\d+', "`${1}$Port"))
    }
    Copy-Item (Join-Path $PSScriptRoot 'PASANG.txt') (Join-Path $isi 'PASANG.txt')

    $sidik = Sidik-Folder $isi
    $jumlah = "$($sidik.Count) file"
    if ((Test-Path $catatan) -and -not $Penuh) {
        Write-Host '== 2b. Memilih file yang berubah'
        $lama = @{}
        (Get-Content $catatan -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $lama[$_.Name] = $_.Value }
        $berubah = @($sidik.Keys | Where-Object { $lama[$_] -ne $sidik[$_] })
        # .env tidak pernah dihapus dari server. Dengan -TanpaEnv sidik lamanya tetap dicatat.
        $hilang = @($lama.Keys | Where-Object { -not $sidik.ContainsKey($_) -and $_ -notlike '*.env' })
        foreach ($k in @($lama.Keys | Where-Object { -not $sidik.ContainsKey($_) -and $_ -like '*.env' })) { $sidik[$k] = $lama[$k] }
        if (-not $berubah -and -not $hilang) {
            Remove-Item $isi -Recurse -Force
            Write-Host 'Tidak ada file yang berubah sejak paket terakhir. Zip tidak dibuat.' -ForegroundColor Yellow
            exit 0
        }
        foreach ($k in @($sidik.Keys | Where-Object { $berubah -notcontains $_ })) {
            $p = Join-Path $isi $k
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
        }
        Get-ChildItem $isi -Recurse -Directory -Force | Sort-Object { $_.FullName.Length } -Descending |
            Where-Object { -not (Get-ChildItem $_.FullName -Force) } | Remove-Item -Force
        if ($hilang) { [IO.File]::WriteAllLines((Join-Path $isi 'HAPUS.txt'), [string[]]($hilang | Sort-Object)) }
        $berubah | Sort-Object | ForEach-Object { Write-Host "  $_" }
        $hilang | Sort-Object | ForEach-Object { Write-Host "  dihapus: $_" }
        if ($berubah | Where-Object { $_ -like '*.env' }) { Write-Warning 'Ada .env yang berubah dan ikut paket. Pengaturan khusus di server akan tertimpa.' }
        $nama = $nama -replace '^CPOS-Platform-', 'CPOS-Platform-perubahan-'
        $jumlah = "$($berubah.Count) file berubah, $($hilang.Count) dihapus"
    }

    Write-Host '== 3. Membuat zip'
    New-Item -ItemType Directory -Force $keluar | Out-Null
    $zip = Join-Path $keluar "$nama.zip"
    Compress-Archive -Path (Join-Path $isi '*') -DestinationPath $zip -CompressionLevel Optimal
    Remove-Item $isi -Recurse -Force
    Simpan-Catatan $sidik $catatan
    $mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Host ''
    Write-Host "Selesai: $zip ($mb MB, $jumlah)" -ForegroundColor Green
    if (-not $TanpaEnv -and ($jumlah -notlike '*berubah*' -or ($berubah | Where-Object { $_ -like '*.env' }))) { Write-Warning 'Zip berisi file .env (password database). Simpan dan kirim hanya lewat jalur internal.' }
}
catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
