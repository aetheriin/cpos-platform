# Membuat paket deploy (zip) CPOS Platform untuk dipasang di PC lain. Dipanggil oleh deploy\buat_paket.bat.
# Isi: backend\ (CPOS + RekapIn, Analytics, Deteksi), frontend\cpos\templates dan static, frontend\analytics\dist (dibangun ulang di sini),
# skrip jalankan & deploy, dan backend\.env yang sekarang (-TanpaEnv: tidak ikut, isi sendiri di PC tujuan dari backend\.env.example).
# Tidak ikut: venv, node_modules, log, upload, cache laporan, sumber frontend (src, package.json, tailwind), docs, lama.
# Hasil: deploy\paket\CPOS-Platform-<tanggal-jam>.zip. Pasang di PC tujuan: ekstrak ke mis. C:\CPOS-Platform, lalu
# klik kanan deploy\pasang.bat > Run as administrator (lihat PASANG.txt di dalam zip).
# -Port 8080: port CPOS di .env dalam paket (PORT), dan Deteksi Plat di port internal -PortDeteksi (DETEKTOR_PORT, URL_DETEKTOR) yang hanya
# bisa dihubungi dari PC itu (CPOS meneruskan videonya). backend\.env di folder ini tidak berubah.
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
        $bangun = Join-Path $kerja 'bangun-frontend\analytics'   # sama dengan bangun-frontend.bat
        robocopy (Join-Path $akar 'frontend\analytics') $bangun /E /XD node_modules dist /NFL /NDL /NJH /NJS /NP | Out-Null
        Push-Location $bangun
        try {
            & npm install --no-audit --no-fund --loglevel=error
            if ($LASTEXITCODE -ne 0) { throw 'npm install gagal' }
            & npm run build
            if ($LASTEXITCODE -ne 0) { throw 'npm run build gagal' }
        } finally { Pop-Location }
        robocopy (Join-Path $bangun 'dist') (Join-Path $akar 'frontend\analytics\dist') /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    }
    if (-not (Test-Path (Join-Path $akar 'frontend\analytics\dist\index.html'))) { throw 'frontend\analytics\dist belum ada. Jalankan tanpa -TanpaBangun.' }

    Write-Host '== 2. Menyalin file'
    Push-Location $akar
    try {
        $daftar = & git -c safe.directory=* ls-files --cached --others --exclude-standard
        if ($LASTEXITCODE -ne 0 -or -not $daftar) { throw 'git ls-files gagal. Pastikan Git terpasang dan folder ini repo git.' }
    } finally { Pop-Location }
    # Dari frontend hanya yang dipakai saat berjalan: templates & static CPOS (dirender Flask) dan dist Analytics (disalin di bawah)
    $daftar = $daftar | Where-Object { $_ -notlike 'frontend/*' -or $_ -like 'frontend/cpos/templates/*' -or $_ -like 'frontend/cpos/static/*' } |
                        Where-Object { $_ -notlike 'deploy/paket/*' -and $_ -notlike 'backend/deteksi/foto_bukti/*' -and
                                       $_ -notlike 'lama/*' -and $_ -notlike 'docs/*' -and $_ -notlike 'frontend/cpos/static/uploads/*' }
    if (Test-Path $isi) { Remove-Item $isi -Recurse -Force }
    foreach ($f in $daftar) {
        $sumber = Join-Path $akar $f
        if (-not (Test-Path $sumber -PathType Leaf)) { continue }        # file terhapus yang belum di-commit
        $tujuan = Join-Path $isi $f
        New-Item -ItemType Directory -Force (Split-Path $tujuan) | Out-Null
        Copy-Item $sumber $tujuan
    }
    robocopy (Join-Path $akar 'frontend\analytics\dist') (Join-Path $isi 'frontend\analytics\dist') /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    if (-not $TanpaEnv) {
        $f = 'backend\.env'
        if (Test-Path (Join-Path $akar $f)) { Copy-Item (Join-Path $akar $f) (Join-Path $isi $f) }
    }
    if ($Port -and -not $TanpaEnv) {
        # diganti bila ada, ditambahkan bila belum (.env hanya berisi yang berbeda dari bawaan); URL_DETEKTOR ikut DETEKTOR_PORT
        $f = Join-Path $isi 'backend\.env'
        $t = [IO.File]::ReadAllText($f) -replace '(?m)^URL_DETEKTOR=.*\r?\n?', ''
        foreach ($kv in @(@('PORT', $Port), @('DETEKTOR_PORT', $PortDeteksi))) {
            if ($t -match "(?m)^$($kv[0])=") { $t = $t -replace "(?m)^$($kv[0])=.*$", "$($kv[0])=$($kv[1])" }
            else { $t = $t.TrimEnd() + "`r`n$($kv[0])=$($kv[1])`r`n" }
        }
        [IO.File]::WriteAllText($f, $t)
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
