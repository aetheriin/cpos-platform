# Menjalankan backend deteksi plat di PC ini. Dipanggil oleh jalankan.bat.
# - Python & library disimpan di PC ini (%LOCALAPPDATA%\deteksi-plat), bukan di folder bersama.
#   Pertama kali dijalankan (atau setelah requirements.txt berubah) library & model AI dipasang otomatis.
# - jalankan.bat           -> deteksi + web (http://IP-PC-ini:8000)
# - jalankan.bat cek       -> cek sambungan kamera saja (tanpa AI)
# - Tutup jendela ini (atau Ctrl+C) untuk berhenti.
$ErrorActionPreference = 'Stop'
$akar = $PSScriptRoot
$lokal = Join-Path $env:LOCALAPPDATA 'deteksi-plat'
$venv = Join-Path $lokal 'venv'
$py = Join-Path $venv 'Scripts\python.exe'
$tanda = Join-Path $venv 'terpasang.txt'
$Host.UI.RawUI.WindowTitle = 'Deteksi Plat'
New-Item -ItemType Directory -Force $lokal | Out-Null

function Cari-Python {
    # Butuh Python 3.10 / 3.11 64-bit
    foreach ($v in '3.11', '3.10') {
        $ErrorActionPreference = 'Continue'
        $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    }
    throw 'Python 3.11 belum terpasang di PC ini. Unduh "Windows installer (64-bit)" Python 3.11 dari python.org (centang Add python.exe to PATH), pasang, lalu jalankan lagi.'
}

try {
    Set-Location $akar
    if (-not (Test-Path (Join-Path $akar '.env'))) {
        Copy-Item (Join-Path $akar '.env.example') (Join-Path $akar '.env')
        throw 'File .env baru dibuat dari .env.example. Isi dulu (kamera, SQL, folder foto), lalu jalankan lagi.'
    }

    $sidik = (Get-FileHash (Join-Path $akar 'requirements.txt')).Hash
    $jalan = $false
    if (Test-Path $py) {
        $ErrorActionPreference = 'Continue'
        & $py -c "import sys" 2>$null | Out-Null
        $jalan = $LASTEXITCODE -eq 0
        $ErrorActionPreference = 'Stop'
    }
    if (-not ($jalan -and (Test-Path $tanda) -and (Get-Content $tanda -Raw).Trim() -eq $sidik)) {
        if (-not $jalan) {
            Write-Host 'Membuat Python untuk Deteksi Plat di PC ini (sekali saja)...'
            if (Test-Path $venv) { Remove-Item $venv -Recurse -Force }
            & (Cari-Python) -m venv $venv
        }
        Write-Host 'Memasang library (pertama kali bisa beberapa menit)...'
        & $py -m pip install --disable-pip-version-check -q --upgrade pip
        & $py -m pip install --disable-pip-version-check -q -r (Join-Path $akar 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Gagal memasang library. Periksa koneksi internet lalu jalankan lagi.' }
        Write-Host 'Mengunduh model AI...'
        & $py -c "from anpr.konfigurasi import muat_konfigurasi; from anpr.pembaca import PembacaPlat; PembacaPlat(muat_konfigurasi())"
        if ($LASTEXITCODE -ne 0) { throw 'Gagal memuat model. Bila error DLL, pasang Microsoft Visual C++ Redistributable x64: https://aka.ms/vs/17/release/vc_redist.x64.exe' }
        Set-Content $tanda $sidik
    }

    if ($args.Count -gt 0 -and $args[0] -eq 'cek') {
        $sisa = @($args | Select-Object -Skip 1)
        & $py baca_plat.py --cek @sisa
        return
    }
    Write-Host ''
    Write-Host 'Deteksi plat berjalan. Tutup jendela ini (atau Ctrl+C) untuk berhenti.' -ForegroundColor Green
    Write-Host ''
    & $py server_web.py @args
}
catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
}