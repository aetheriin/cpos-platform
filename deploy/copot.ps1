# Menghentikan dan melepas tugas terjadwal "CPOS Platform" serta aturan firewall-nya. Dipanggil oleh deploy\copot.bat.
# Yang dimatikan hanya Python paket ini: dari folder ProgramData, atau yang memegang port paket ini. Aplikasi lain di PC ini tidak disentuh.
$akar = Split-Path $PSScriptRoot -Parent

function Port-Dari($berkas, $nama, $bawaan) {
    $baris = Select-String (Join-Path $akar $berkas) -Pattern "^\s*$nama\s*=\s*(\d+)" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($baris) { return [int]$baris.Matches[0].Groups[1].Value }
    return $bawaan
}

Stop-ScheduledTask -TaskName 'CPOS Platform' -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'CPOS Platform' -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.ExecutablePath -like "$env:ProgramData\CPOS-Platform\*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
foreach ($p in (Port-Dari 'CPOS\.env' 'PORT' 8080), 8001, (Port-Dari 'Deteksi\.env' 'PORT_WEB' 8002)) {
    Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object {
        Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue | Where-Object ProcessName -eq 'python' | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}
Get-NetFirewallRule -DisplayName 'CPOS Platform port *' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
'CPOS Platform sudah dihentikan dan dilepas.'
