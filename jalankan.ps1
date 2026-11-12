# Menjalankan semua aplikasi di PC ini: CPOS (+ RekapIn, + Analytics di /analytics), backend Analytics, dan Deteksi Plat.
# Pengaturan semuanya di backend\.env. Python & library disimpan di %LOCALAPPDATA%\cpos-platform (dibuat sendiri saat pertama kali).
$ErrorActionPreference = 'Stop'
$akar = $PSScriptRoot
$be = Join-Path $akar 'backend'
$fileEnv = Join-Path $be '.env'
$lokal = Join-Path $env:LOCALAPPDATA 'cpos-platform'
$log = Join-Path $lokal 'log'
$PortAnalytics = 8001
$PortDeteksi = 8000
$JalankanDeteksi = $true
New-Item -ItemType Directory -Force $log | Out-Null
$Host.UI.RawUI.WindowTitle = 'CPOS Platform'

function Cari-Python {
    # CPOS butuh Python 3.10 / 3.11 (mediapipe 0.10.9)
    foreach ($v in '3.11', '3.10') {
        $ErrorActionPreference = 'Continue'
        $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    }
    throw 'Python 3.11 belum terpasang di PC ini. Unduh "Windows installer (64-bit)" Python 3.11 dari python.org, pasang, lalu jalankan lagi.'
}

function Siapkan-Venv($nama, $folder, $requirements, $tambahan) {
    $py = Join-Path $folder 'Scripts\python.exe'
    $tanda = Join-Path $folder 'terpasang.txt'
    $sidik = ($requirements | ForEach-Object { (Get-FileHash $_).Hash }) -join ','
    $jalan = $false
    if (Test-Path $py) {
        $ErrorActionPreference = 'Continue'
        & $py -c "import sys" 2>$null | Out-Null
        $jalan = $LASTEXITCODE -eq 0
        $ErrorActionPreference = 'Stop'
    }
    if ($jalan -and (Test-Path $tanda) -and (Get-Content $tanda -Raw).Trim() -eq $sidik) { return $py }
    if (-not $jalan) {
        Write-Host "Membuat Python untuk $nama di PC ini (sekali saja)..."
        if (Test-Path $folder) { Remove-Item $folder -Recurse -Force }
        & (Cari-Python) -m venv $folder
    }
    Write-Host "Memasang library $nama (pertama kali bisa beberapa menit)..."
    & $py -m pip install --disable-pip-version-check -q --upgrade pip
    foreach ($r in $requirements) {
        & $py -m pip install --disable-pip-version-check -q -r $r
        if ($LASTEXITCODE -ne 0) { throw "Gagal memasang library dari $r. Periksa koneksi internet lalu jalankan lagi." }
    }
    foreach ($perintah in $tambahan) {
        & $py -m pip install --disable-pip-version-check -q @perintah
        if ($LASTEXITCODE -ne 0) { throw "Gagal memasang $($perintah -join ' ')." }
    }
    Set-Content $tanda $sidik
    return $py
}

function Hentikan-Sisa {
    # Python dari venv PC ini yang masih hidup (jendela ditutup paksa sebelumnya). python.exe venv hanya peluncur: proses sebenarnya memakai
    # python.exe induk di luar folder venv, jadi yang memegang port aplikasi ini juga dimatikan. Aplikasi lain di PC ini tidak disentuh.
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.ExecutablePath -and ($_.ExecutablePath -like "$lokal\venv-*" -or $_.ExecutablePath -like "$env:LOCALAPPDATA\deteksi-plat\venv\*") } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    foreach ($p in $portCpos, $PortAnalytics, $PortDeteksi) {
        Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object {
            Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue | Where-Object ProcessName -eq 'python' | Stop-Process -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 500
}

function Port-Dipakai($port) {
    # PID 0 (Idle) = sisa socket proses yang baru ditutup; Windows melepasnya sendiri dalam beberapa detik, jadi ditunggu, bukan ditolak
    for ($i = 0; $i -lt 20; $i++) {
        $semua = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
        $c = $semua | Where-Object OwningProcess -ne 0 | Select-Object -First 1
        if ($c -or $semua.Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    }
    if ($c) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        throw "Port $port sudah dipakai $($p.ProcessName) (PID $($c.OwningProcess)), mungkin CPOS/Analytics yang dijalankan manual. Tutup dulu, atau: Stop-Process -Id $($c.OwningProcess)"
    }
}

function Nilai-Env($nama, $bawaan) {
    $baris = Select-String $fileEnv -Pattern "^\s*$nama\s*=\s*(\d+)" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($baris) { return [int]$baris.Matches[0].Groups[1].Value }
    return $bawaan
}

function Tunggu-Port($port, $nama, $detik = 90) {
    for ($i = 0; $i -lt $detik; $i++) {
        $tcp = New-Object Net.Sockets.TcpClient
        try { $tcp.Connect('127.0.0.1', $port); return $true } catch { Start-Sleep 1 } finally { $tcp.Dispose() }
    }
    return $false
}

try {
    if (-not (Test-Path $fileEnv)) {
        Copy-Item (Join-Path $be ".env.example") $fileEnv
        throw "File $fileEnv baru dibuat dari contoh. Isi dulu (database, SECRET_KEY, dll), lalu jalankan lagi."
    }
    $portCpos = Nilai-Env 'PORT' 5000
    # Deteksi hanya diakses oleh CPOS di PC yang sama
    $PortDeteksi = Nilai-Env 'DETEKTOR_PORT' $PortDeteksi
    $hostDeteksi = '127.0.0.1'

    # Library modul CPOS (mis. modules\item_request\requirements.txt) ikut dipasang ke Python CPOS; modul baru otomatis ikut
    $reqCpos = @(Join-Path $be 'cpos\requirements.txt') + @(Get-ChildItem (Join-Path $be 'cpos\modules') -Recurse -Filter 'requirements.txt' |
        Sort-Object FullName | ForEach-Object FullName)
    $pyCpos = Siapkan-Venv 'CPOS' (Join-Path $lokal 'venv-cpos') $reqCpos @(, @('--no-deps', 'face-recognition==1.3.0'))
    $pyAnalytics = Siapkan-Venv 'Analytics' (Join-Path $lokal 'venv-analytics') @(Join-Path $be 'analytics\requirements.txt') @()
    $adaDeteksi = $JalankanDeteksi -and (Test-Path (Join-Path $be 'deteksi\server_web.py'))
    if ($adaDeteksi) {
        $pyDeteksi = Siapkan-Venv 'Deteksi Plat' (Join-Path $env:LOCALAPPDATA 'deteksi-plat\venv') @(Join-Path $be 'deteksi\requirements.txt') @()
    }
    if (-not (Test-Path (Join-Path $akar 'frontend\analytics\dist\index.html'))) {
        Write-Warning 'Tampilan Analytics belum dibangun: laporan tidak akan tampil. Jalankan bangun-frontend.bat sekali.'
    }

    Hentikan-Sisa
    Port-Dipakai $portCpos
    Port-Dipakai $PortAnalytics
    if ($adaDeteksi) { Port-Dipakai $PortDeteksi }

    Write-Host 'Menyalakan backend Analytics...'
    $analytics = Start-Process $pyAnalytics -ArgumentList '-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', $PortAnalytics `
        -WorkingDirectory (Join-Path $be 'analytics') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $log 'analytics.log') -RedirectStandardError (Join-Path $log 'analytics-galat.log')
    if (-not (Tunggu-Port $PortAnalytics 'Analytics' 60)) { throw "Backend Analytics gagal menyala. Lihat $log\analytics-galat.log" }
    if ($adaDeteksi) {
        Write-Host 'Menyalakan backend Deteksi Plat...'
        $env:PYTHONUNBUFFERED = '1'
        $deteksi = Start-Process $pyDeteksi -ArgumentList 'server_web.py', '--port', $PortDeteksi, '--host', $hostDeteksi -WorkingDirectory (Join-Path $be 'deteksi') -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $log 'deteksi.log') -RedirectStandardError (Join-Path $log 'deteksi-galat.log')
        if (-not (Tunggu-Port $PortDeteksi 'Deteksi' 60)) {
            Write-Warning "Backend Deteksi belum siap (model AI masih dimuat, atau ada galat). Lihat $log\deteksi-galat.log. CPOS tetap dijalankan."
        }
    }

    # browser dibuka setelah CPOS siap
    Start-Job -ArgumentList $portCpos -ScriptBlock {
        param($port)
        for ($i = 0; $i -lt 120; $i++) {
            $tcp = New-Object Net.Sockets.TcpClient
            try { $tcp.Connect('127.0.0.1', $port); Start-Process "http://localhost:$port"; return } catch { Start-Sleep 1 } finally { $tcp.Dispose() }
        }
    } | Out-Null

    Write-Host ''
    Write-Host "CPOS + Analytics: http://localhost:$portCpos   (dari PC lain: http://<IP PC ini>:$portCpos)" -ForegroundColor Green
    if ($deteksi) { Write-Host "Deteksi Plat: http://localhost:$PortDeteksi   (log: $log\deteksi.log)" -ForegroundColor Green }
    Write-Host 'Tutup jendela ini untuk berhenti.' -ForegroundColor Green
    Write-Host ''
    Set-Location (Join-Path $be 'cpos')
    & $pyCpos serve.py
}
catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
}
finally {
    if ($analytics -and -not $analytics.HasExited) { & taskkill /PID $analytics.Id /T /F | Out-Null }
    if ($deteksi -and -not $deteksi.HasExited) { & taskkill /PID $deteksi.Id /T /F | Out-Null }
}
