$ErrorActionPreference = 'Stop'
try {
    $base = Join-Path $env:ProgramData 'ManagerPC-Agent'
    if (Get-ScheduledTask -TaskName 'ManagerPC Agent' -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName 'ManagerPC Agent' -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName 'ManagerPC Agent' -Confirm:$false
    }
    Remove-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -Name 'ManagerPC Desktop' -ErrorAction SilentlyContinue
    $ownedPaths = @((Join-Path $base 'ManagerPC-Agent.exe'), (Join-Path $base 'ManagerPC-Desktop.exe'))
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and ($ownedPaths -contains $_.ExecutablePath) } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    $agent = Join-Path $base 'ManagerPC-Agent.exe'
    if (Test-Path -LiteralPath (Join-Path $base 'browser-rules.json')) {
        $process = Start-Process -FilePath $agent -ArgumentList '--remove-browser-rules' -Wait -PassThru -WindowStyle Hidden
        if ($process.ExitCode -ne 0) { throw 'Brauzer qoidalarini olib tashlab bolmadi. install-error.txt ni tekshiring.' }
    }
    $hostsFile = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
    $text = [System.IO.File]::ReadAllText($hostsFile)
    $begin = '# ManagerPC BEGIN'; $end = '# ManagerPC END'
    $start = $text.IndexOf($begin); $finish = $text.IndexOf($end)
    if (($start -ge 0) -and ($finish -gt $start) -and ($text.LastIndexOf($begin) -eq $start) -and ($text.LastIndexOf($end) -eq $finish)) {
        $text = $text.Remove($start, $finish + $end.Length - $start)
        [System.IO.File]::WriteAllText($hostsFile, $text)
        ipconfig /flushdns | Out-Null
    } elseif (($start -ge 0) -or ($finish -ge 0)) { throw 'hosts faylida belgilar buzilgan. Qolda tekshirish kerak.' }
    Write-Host 'Agent, ekran yordamchisi va ManagerPC cheklovlari toxtatildi.' -ForegroundColor Green
    Write-Host 'Sozlamalar va fayllar qayta ornatish uchun ProgramData\ManagerPC-Agent papkasida qoldirildi.'
} catch { Write-Host "Xato: $_" -ForegroundColor Red; exit 1 }
