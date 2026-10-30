$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m PyInstaller --onefile --noconsole --name ManagerPC-Agent --distpath . --workpath build\agent4 --specpath build agent_v4.py
    if ($LASTEXITCODE) { throw 'Agent build failed' }
    python -m PyInstaller --onefile --noconsole --name ManagerPC-Desktop --distpath . --workpath build\desktop4 --specpath build desktop_agent.py
    if ($LASTEXITCODE) { throw 'Desktop build failed' }
    python -m PyInstaller --onefile --name ManagerPC-Admin-4 --distpath . --workpath build\admin4 --specpath build server_v4.py
    if ($LASTEXITCODE) { throw 'Admin build failed' }
} finally { Pop-Location }
