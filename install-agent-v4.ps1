$ErrorActionPreference = 'Stop'
try {
    $base = Join-Path $env:ProgramData 'ManagerPC-Agent'
    $serviceDir = Join-Path $base 'service'
    foreach ($name in @('ManagerPC-Agent.exe', 'ManagerPC-Desktop.exe', 'enrollment.json', 'server-cert.pem')) {
        if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $name))) {
            throw "Paket to'liq emas: $name. Admin paneldagi O'rnatish bo'limidan yangi ZIP oling va uni papkaga chiqaring."
        }
    }
    New-Item -ItemType Directory -Force -Path $base | Out-Null
    & icacls.exe $base /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Agent papkasi ruxsatlarini sozlab bolmadi.' }
    New-Item -ItemType Directory -Force -Path $serviceDir | Out-Null
    & icacls.exe $serviceDir /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Maxfiy sozlamalar ruxsatlarini sozlab bolmadi.' }
    # Pair successfully before stopping an already installed agent.
    $enrollment = Start-Process -FilePath (Join-Path $PSScriptRoot 'ManagerPC-Agent.exe') -ArgumentList @('--enroll', ('"' + $PSScriptRoot + '"')) -Wait -PassThru -WindowStyle Hidden
    if ($enrollment.ExitCode -ne 0) {
        $errorFile = Join-Path $base 'install-error.txt'
        $detail = if (Test-Path -LiteralPath $errorFile) { Get-Content -LiteralPath $errorFile -Raw } else { 'Agent admin serverga ulanmadi.' }
        throw $detail
    }
    if (Get-ScheduledTask -TaskName 'ManagerPC Agent' -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName 'ManagerPC Agent' -ErrorAction SilentlyContinue
    }
    $ownedPaths = @((Join-Path $base 'ManagerPC-Agent.exe'), (Join-Path $base 'ManagerPC-Desktop.exe'))
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and ($ownedPaths -contains $_.ExecutablePath) } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    foreach ($name in @('ManagerPC-Agent.exe', 'ManagerPC-Desktop.exe')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $base $name) -Force
    }
    $agentExe = Join-Path $base 'ManagerPC-Agent.exe'
    $action = New-ScheduledTaskAction -Execute $agentExe -WorkingDirectory $base
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName 'ManagerPC Agent' -Action $action -Trigger $trigger -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
    $runKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
    New-ItemProperty -Path $runKey -Name 'ManagerPC Desktop' -Value ('"' + (Join-Path $base 'ManagerPC-Desktop.exe') + '"') -PropertyType String -Force | Out-Null
    Start-ScheduledTask -TaskName 'ManagerPC Agent'
    Write-Host "Tayyor. Agent ulandi. Ekran yordamchisi uchun Windows hisobidan chiqib qayta kiring." -ForegroundColor Green
    Write-Host "Keyingi safar agent va ekran yordamchisi avtomatik ishlaydi. Python yoki Veyon kerak emas."
} catch {
    Write-Host "Xato: $_" -ForegroundColor Red
    Write-Host "Admin panel ochiq ekanini va TCP 8766 portiga ruxsat borligini tekshiring."
    exit 1
}
