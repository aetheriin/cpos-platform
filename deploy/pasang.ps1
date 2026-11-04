# Memasang CPOS Platform di PC ini sebagai tugas terjadwal yang menyala sendiri saat Windows menyala (tanpa perlu login).
# Dipanggil oleh deploy\pasang.bat (Run as administrator). Aman dijalankan ulang, mis. setelah memperbarui file aplikasi.
#  1. Python 3.11 (untuk semua user) dan ODBC Driver 18 for SQL Server: dipasang lewat winget bila belum ada
#  2. File .env CPOS, Analytics, Deteksi: harus sudah ada (ikut paket, atau salin dari .env.example lalu isi)
#  3. Firewall: hanya port CPOS yang dibuka untuk PC lain; Analytics dan Deteksi Plat diakses lewat CPOS
#  4. Tugas terjadwal "CPOS Platform": akun SYSTEM, saat Windows menyala, menyala ulang bila berhenti
#  5. Menyalakan tugasnya sekarang dan menunggu CPOS siap (pertama kali memasang library Python, bisa 10-20 menit)
$ErrorActionPreference = 'Stop'
$akar = Split-Path $PSScriptRoot -Parent
$NamaTugas = 'CPOS Platform'
$data = Join-Path $env:ProgramData 'CPOS-Platform'
$log = Join-Path $data 'cpos-platform\log'

function Langkah($teks) { Write-Host ''; Write-Host "== $teks" -ForegroundColor Cyan }

function Ada-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'winget tidak tersedia di PC ini. Pasang manual: Python 3.11 64-bit (centang "Install for all users") dan ODBC Driver 18 for SQL Server, lalu jalankan pasang.bat lagi.'
    }
}

function Python-Semua-User {
    # Tugas berjalan sebagai SYSTEM, jadi Python harus terpasang untuk semua user (py.exe di C:\Windows)
    $py = Join-Path $env:WINDIR 'py.exe'
    if (Test-Path $py) {
        $ErrorActionPreference = 'Continue'
        & $py -3.11 -c "import sys" 2>$null
        $ok = $LASTEXITCODE -eq 0
        $ErrorActionPreference = 'Stop'
        if ($ok) { return }
    }
    Write-Host 'Python 3.11 untuk semua user belum ada, memasang lewat winget...'
    Ada-Winget
    & winget install --id Python.Python.3.11 --scope machine --exact --silent --accept-package-agreements --accept-source-agreements `
        --override '/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=1'
    if (-not (Test-Path $py)) { throw 'Python 3.11 gagal dipasang. Pasang manual dari python.org (centang "Install for all users"), lalu jalankan lagi.' }
}

function Odbc-18 {
    if (Test-Path 'HKLM:\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 18 for SQL Server') { return }
    Write-Host 'ODBC Driver 18 for SQL Server belum ada, memasang lewat winget...'
    Ada-Winget
    & winget install --id Microsoft.msodbcsql.18 --exact --silent --accept-package-agreements --accept-source-agreements
    if (-not (Test-Path 'HKLM:\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 18 for SQL Server')) {
        throw 'ODBC Driver 18 gagal dipasang. Unduh "ODBC Driver 18 for SQL Server" dari situs Microsoft, pasang, lalu jalankan lagi.'
    }
}

function Cek-Env {
    $kurang = @()
    foreach ($f in 'CPOS\.env', 'Analytics\backend\.env', 'Deteksi\.env') {
        $p = Join-Path $akar $f
        if ((Test-Path (Split-Path $p)) -and -not (Test-Path $p)) {
            Copy-Item ($p + '.example') $p
            $kurang += $f
        }
    }
    if ($kurang) { throw "File berikut baru dibuat dari contoh dan harus diisi dulu (server SQL, password, dll): $($kurang -join ', '). Lalu jalankan pasang.bat lagi." }
}

function Cek-Port-Bebas($porta) {
    # jalankan.ps1 berhenti kalau port terpakai; diperiksa di sini supaya galatnya langsung terlihat
    foreach ($p in $porta) {
        $c = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | Where-Object OwningProcess -ne 0 | Select-Object -First 1
        if ($c) {
            $proses = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            throw "Port $p sudah dipakai $($proses.ProcessName) (PID $($c.OwningProcess), $($proses.Path)). Hentikan program itu dulu, lalu jalankan pasang.bat lagi."
        }
    }
}

function Port-Cpos {
    $baris = Select-String (Join-Path $akar 'CPOS\.env') -Pattern '^\s*PORT\s*=\s*(\d+)' | Select-Object -First 1
    if ($baris) { return [int]$baris.Matches[0].Groups[1].Value }
    return 5000
}

try {
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { throw 'Jalankan pasang.bat dengan klik kanan > Run as administrator.' }
    $port = Port-Cpos
    $adaDeteksi = Test-Path (Join-Path $akar 'Deteksi\server_web.py')

    Langkah '1. Python 3.11 & ODBC Driver 18'
    Python-Semua-User
    Odbc-18

    Langkah '2. File pengaturan (.env)'
    Cek-Env
    Write-Host 'Lengkap.'

    Langkah '3. Firewall'
    $nama = "CPOS Platform port $port"
    Get-NetFirewallRule -DisplayName 'CPOS Platform port *' -ErrorAction SilentlyContinue | Where-Object DisplayName -ne $nama | Remove-NetFirewallRule
    if (-not (Get-NetFirewallRule -DisplayName $nama -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $nama -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow -Profile Domain, Private | Out-Null
    }
    Write-Host "Port $port dibuka untuk jaringan kantor (Domain / Private)."

    Langkah '4. Tugas terjadwal'
    $adaTugas = [bool](Get-ScheduledTask -TaskName $NamaTugas -ErrorAction SilentlyContinue)
    if ($adaTugas) {
        Stop-ScheduledTask -TaskName $NamaTugas -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $NamaTugas -Confirm:$false
    }
    # sisa proses dari tugas sebelumnya (library / file aplikasi mungkin baru diperbarui)
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.ExecutablePath -like "$data\*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $portDeteksi = 8000
    $baris = Select-String (Join-Path $akar 'Deteksi\.env') -Pattern '^\s*PORT_WEB\s*=\s*(\d+)' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($baris) { $portDeteksi = [int]$baris.Matches[0].Groups[1].Value }
    $portApp = @($port, 8001) + $(if ($adaDeteksi) { $portDeteksi } else { @() })
    # Memperbarui pasangan lama: python.exe venv hanya peluncur, proses sebenarnya memakai python induk di luar folder data dan tetap memegang portnya.
    # Pemasangan pertama tidak mematikan apa pun, jadi port yang dipakai aplikasi lain tetap dilaporkan oleh Cek-Port-Bebas.
    if ($adaTugas) {
        foreach ($p in $portApp) {
            Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object {
                Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue | Where-Object ProcessName -eq 'python' | Stop-Process -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Start-Sleep 2
    Cek-Port-Bebas $portApp
    $aksi = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $akar `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'layanan.ps1')`""
    $pemicu = New-ScheduledTaskTrigger -AtStartup
    $pemicu.Delay = 'PT30S'                                   # tunggu jaringan siap
    $aturan = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    $akun = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $NamaTugas -Action $aksi -Trigger $pemicu -Settings $aturan -Principal $akun `
        -Description 'CPOS + RekapIn + Analytics (+ Deteksi Plat). Dipasang oleh deploy\pasang.bat; copot dengan deploy\copot.bat.' | Out-Null
    Write-Host "Tugas '$NamaTugas' terdaftar: menyala sendiri saat Windows menyala, dan dinyalakan ulang bila berhenti."

    Langkah '5. Menyalakan'
    $fileLog = Join-Path $log 'layanan.log'
    $barisAwal = if (Test-Path $fileLog) { @(Get-Content $fileLog).Count } else { 0 }
    Start-ScheduledTask -TaskName $NamaTugas
    Write-Host 'Pertama kali: library Python dipasang dulu (perlu internet, bisa 10-20 menit). Kemajuan di:'
    Write-Host "  $log\layanan.log"
    $siap = $false
    for ($i = 0; $i -lt 1800 -and -not $siap; $i += 5) {
        Start-Sleep 5
        $tcp = New-Object Net.Sockets.TcpClient
        try { $tcp.Connect('127.0.0.1', $port); $siap = $true } catch { } finally { $tcp.Dispose() }
        $galat = Get-Content $fileLog -ErrorAction SilentlyContinue | Select-Object -Skip $barisAwal | Where-Object { $_ -match 'TerminatingError' } | Select-Object -First 1
        if (-not $siap -and $galat) { throw "CPOS gagal menyala: $galat" }
        if (-not $siap -and $i % 60 -eq 0) {
            $akhir = Get-Content (Join-Path $log 'layanan.log') -Tail 1 -ErrorAction SilentlyContinue
            Write-Host "  ... $([int]($i / 60)) menit: $akhir"
        }
    }
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object -First 1).IPAddress
    if ($siap) {
        Write-Host ''
        Write-Host "Selesai. CPOS: http://localhost:$port  (dari PC lain: http://$($ip):$port)" -ForegroundColor Green
    } else {
        Write-Warning "CPOS belum menyala setelah 30 menit. Lihat $log\layanan.log dan $log\analytics-galat.log."
    }
}
catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
