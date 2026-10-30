import io
import json
import os
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(dir=ROOT, prefix='package-test-') as directory:
    os.environ['LOCALAPPDATA'] = directory
    import server_v4 as server
    server.CERT = server.make_certificate(server.DATA)
    bundle = server.package_bytes('192.168.1.10')
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = set(archive.namelist())
        assert 'ManagerPC-Agent.exe' in names and 'ManagerPC-Desktop.exe' in names
        assert 'server-key.pem' not in names and 'config.json' not in names
        enrollment = json.loads(archive.read('enrollment.json'))
        assert enrollment['server'] == 'https://192.168.1.10:8766'
        assert enrollment['fingerprint'] == server.CERT[2]
        assert archive.read('ManagerPC-Agent.exe') == (ROOT / 'ManagerPC-Agent.exe').read_bytes()
        assert archive.read('install-agent.ps1') == (ROOT / 'install-agent.ps1').read_bytes()
    print('Agent ZIP verified: both EXEs, scripts, public certificate, enrollment; no private server key.')
