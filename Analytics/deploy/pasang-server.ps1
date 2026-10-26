# Dijalankan di SERVER (Windows 10 Pro), di PowerShell "Run as administrator", dari folder hasil ekstrak zip:
#   powershell -ExecutionPolicy Bypass -File deploy\pasang-server.ps1
# Aman dijalankan ulang (mis. saat update versi): langkah yang sudah ada dilewati atau diperbarui.
#
# Yang dilakukan:
#   1. Membuat venv backend dan memasang pustaka Python
#   2. Mendaftarkan backend sebagai tugas Windows yang jalan otomatis saat komputer menyala (dan dinyalakan ulang kalau mati)
#   3. Menyalakan proxy di IIS (Application Request Routing) dan membuat situs IIS untuk folder web
param(
    [int]$PortWeb = 80,              # port situs IIS yang dibuka pengguna
    [int]$PortBackend = 8001,        # port backend; harus sama dengan web\web.config
    [string]$NamaSitus = 'DashboardAnalytics',
    [string]$Python = ''             # path python.exe tertentu; kosong = pilih otomatis versi yang didukung
)
$ErrorActionPreference = 'Stop'
$akar = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $akar 'backend'
$web = Join-Path $akar 'web'
$appcmd = "$env:windir\System32\inetsrv\appcmd.exe"

function Periksa($syarat, $pesan) { if (-not $syarat) { throw $pesan } }

# ---------- 0. Prasyarat ----------
# pyodbc (penghubung ke SQL Server) hanya punya paket siap pakai untuk versi Python yang sudah dirilis cukup lama. Versi yang lebih baru
# memaksa pip merakitnya sendiri dan gagal tanpa Visual C++. Jadi dipilih versi terbaru yang masih didukung lewat launcher "py".
$VERSI_DIDUKUNG = @('3.14', '3.13', '3.12', '3.11')
# Menjalankan program dan mengambil keluarannya; error (mis. versi itu tidak terpasang) dianggap kosong, bukan menghentikan skrip
function Coba([scriptblock]$perintah) {
    $lama = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
    try { $hasil = & $perintah 2>$null; if ($LASTEXITCODE -eq 0 -and $hasil) { "$hasil".Trim() } } catch { $null } finally { $ErrorActionPreference = $lama }
}
function VersiPython($exe) { Coba { & $exe -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" } }
$python = $Python
if (-not $python -and (Get-Command py -ErrorAction SilentlyContinue)) {
    foreach ($v in $VERSI_DIDUKUNG) {
        $python = Coba { & py "-$v" -c "import sys; print(sys.executable)" }
        if ($python) { break }
    }
}
if (-not $python) { $python = (Get-Command python -ErrorAction SilentlyContinue).Source }
Periksa $python 'Python belum terpasang. Pasang Python 3.14 dari python.org (centang "Add python.exe to PATH"), lalu buka PowerShell baru.'
$versi = VersiPython $python
Periksa ($VERSI_DIDUKUNG -contains $versi) ("Python yang ditemukan versi $versi ($python), belum didukung pyodbc. Pasang Python 3.14 dari python.org " +
    '(boleh berdampingan dengan versi lain), lalu jalankan skrip ini lagi.')
Write-Host "   Memakai Python $versi ($python)"
Periksa (Test-Path $appcmd) 'IIS belum aktif. Nyalakan lewat "Turn Windows features on or off" -> Internet Information Services (lihat panduan langkah 2).'
Periksa (Test-Path "$env:windir\System32\inetsrv\rewrite.dll") 'Modul IIS URL Rewrite belum terpasang (lihat panduan langkah 2).'
Periksa (Test-Path "$env:ProgramFiles\IIS\Application Request Routing") 'Modul IIS Application Request Routing (ARR) belum terpasang (lihat panduan langkah 2).'
Periksa (Test-Path (Join-Path $backend '.env')) "File backend\.env belum ada. Buat dulu (lihat panduan langkah 4)."
$driver = Get-OdbcDriver -ErrorAction SilentlyContinue | Where-Object Name -eq 'ODBC Driver 18 for SQL Server'
Periksa $driver 'ODBC Driver 18 for SQL Server belum terpasang (lihat panduan langkah 2).'

# ---------- 1. venv dan pustaka ----------
Write-Host '1/3 Memasang pustaka Python...'
$venvPy = Join-Path $backend 'venv\Scripts\python.exe'
# venv dari versi Python lain (mis. percobaan sebelumnya dengan 3.15) dibuat ulang
if ((Test-Path $venvPy) -and (VersiPython $venvPy) -ne $versi) {
    Write-Host "   venv lama memakai Python lain, dibuat ulang..."
    Remove-Item (Join-Path $backend 'venv') -Recurse -Force
}
if (-not (Test-Path $venvPy)) { & $python -m venv (Join-Path $backend 'venv') }
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install --no-cache-dir -r (Join-Path $backend 'requirements.txt')
Periksa ($LASTEXITCODE -eq 0) 'pip install gagal. Baca pesan error di atas: biasanya koneksi internet server, atau versi Python yang belum didukung.'
Push-Location $backend
try { & $venvPy -m inti.alat_pengguna cek } finally { Pop-Location }

# ---------- 2. Backend sebagai tugas Windows ----------
Write-Host '2/3 Mendaftarkan backend...'
$namaTugas = 'DashboardAnalytics-Backend'
# Keluaran backend (termasuk error) ditulis ke backend\server.log, karena tugas berjalan tanpa jendela
$log = Join-Path $backend 'server.log'
$aksi = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $backend `
    -Argument "/c `"`"$venvPy`" -m uvicorn api:app --host 127.0.0.1 --port $PortBackend >> `"$log`" 2>&1`""
$pemicu = New-ScheduledTaskTrigger -AtStartup
$aturan = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
$pelaku = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
if (Get-ScheduledTask -TaskName $namaTugas -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $namaTugas -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $namaTugas -Confirm:$false
}
Register-ScheduledTask -TaskName $namaTugas -Action $aksi -Trigger $pemicu -Settings $aturan -Principal $pelaku | Out-Null
Start-ScheduledTask -TaskName $namaTugas
Start-Sleep -Seconds 8
try {
    $status = Invoke-RestMethod "http://127.0.0.1:$PortBackend/api/status" -TimeoutSec 10
    Write-Host "   Backend menyala: $($status.nama)"
} catch {
    throw "Backend tidak menjawab di port $PortBackend. Lihat errornya di $log"
}

# ---------- 3. IIS ----------
Write-Host '3/3 Mengatur IIS...'
& $appcmd set config -section:system.webServer/proxy /enabled:"True" /timeout:"00:10:00" /preserveHostHeader:"True" /commit:apphost | Out-Null
# Port web tidak boleh sudah dipakai situs IIS lain (biasanya "Default Web Site" di port 80)
$daftarSitus = [xml]((& $appcmd list site /xml) -join "`n")         # keluaran appcmd digabung dulu jadi satu dokumen XML
$lain = @($daftarSitus.SelectNodes('//SITE') |
    Where-Object { $_.'SITE.NAME' -ne $NamaSitus -and $_.bindings -match ":${PortWeb}:" -and $_.state -eq 'Started' })
if ($lain) {
    throw "Port $PortWeb sudah dipakai situs IIS '$($lain[0].'SITE.NAME')'. Hentikan situs itu di IIS Manager, atau jalankan ulang dengan -PortWeb 8080."
}
if (& $appcmd list site /name:$NamaSitus) {
    & $appcmd set vdir "$NamaSitus/" /physicalPath:"$web" | Out-Null
} else {
    & $appcmd add site /name:$NamaSitus /bindings:"http/*:${PortWeb}:" /physicalPath:"$web" | Out-Null
}
& $appcmd start site /site.name:$NamaSitus | Out-Null
icacls $web /grant 'IIS_IUSRS:(OI)(CI)RX' /T /Q | Out-Null      # IIS harus bisa membaca folder web
if (-not (Get-NetFirewallRule -DisplayName "Dashboard Analytics (port $PortWeb)" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Dashboard Analytics (port $PortWeb)" -Direction Inbound -Protocol TCP -LocalPort $PortWeb -Action Allow | Out-Null
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
Write-Host ''
Write-Host 'Selesai.'
Write-Host "  Di server ini : http://localhost$(if ($PortWeb -ne 80) { ":$PortWeb" })"
Write-Host "  Dari komputer lain : http://$ip$(if ($PortWeb -ne 80) { ":$PortWeb" })"
