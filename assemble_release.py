"""Package an explicit allowlist; never include server certificates or device keys."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT / 'release' / 'ManagerPC-4'
FILES = ['ManagerPC-Admin-4.exe', 'ManagerPC-Agent.exe', 'ManagerPC-Desktop.exe',
         'index.html', 'app.js', 'style.css', 'AGENT-INSTALL.bat', 'install-agent.ps1',
         'AGENT-REMOVE.bat', 'remove-agent.ps1', 'ADMIN-FIREWALL.bat', 'README.md']
RELEASE.mkdir(parents=True, exist_ok=True)
for name in FILES: shutil.copy2(ROOT / name, RELEASE / name)
(RELEASE / 'ADMIN-START.bat').write_text('@echo off\ncd /d "%~dp0"\n"%~dp0ManagerPC-Admin-4.exe"\npause\n', encoding='ascii')
(RELEASE / 'BOSHLASH.txt').write_text('MANAGERPC 4\n\n1. Eski admin oynasini yoping.\n2. ADMIN-START.bat ni oching.\n3. ADMIN-FIREWALL.bat ni admin kompyuterda Run as administrator bilan bir marta oching.\n4. Paneldagi Ornatish bolimida admin IP manzilini yozib agent ZIP paketini oling.\n5. Shu ZIP ni oquvchi PC da chiqaring, AGENT-INSTALL.bat ni administrator sifatida oching.\n6. Oquvchi Windows hisobidan chiqib qayta kirsin.\n\nPython va Veyon kerak emas. Eski 1.x agentlarni yangi paketdan yangilang.\nAvval bitta oquvchi kompyuterida sinang. Batafsil: README.md\n', encoding='utf-8')
notices = ['ManagerPC bundles the Python runtime and third-party open-source components.\n']
python_license = Path(sys.prefix) / 'LICENSE.txt'
if python_license.exists(): notices.append('PYTHON\n' + python_license.read_text(encoding='utf-8'))
for name in ('Pillow', 'psutil', 'pywin32', 'cryptography', 'pyinstaller', 'numpy'):
    try:
        package = importlib.metadata.distribution(name)
        notices.append('\n' + name + ' ' + package.version)
        for path in package.files or []:
            if any(word in str(path).lower() for word in ('license', 'copying')) and '.dist-info/' in str(path):
                file = package.locate_file(path)
                if file.is_file() and file.stat().st_size < 300000:
                    notices.append(str(path) + '\n' + file.read_text(encoding='utf-8', errors='replace'))
    except importlib.metadata.PackageNotFoundError: pass
(RELEASE / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices), encoding='utf-8')
files = FILES + ['ADMIN-START.bat', 'BOSHLASH.txt', 'THIRD-PARTY-NOTICES.txt']
checksums = {name: hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() for name in files}
(RELEASE / 'SHA256.json').write_text(json.dumps(checksums, indent=2), encoding='utf-8')
files.append('SHA256.json')
with zipfile.ZipFile(ROOT / 'release' / 'ManagerPC-4.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for name in files: archive.write(RELEASE / name, 'ManagerPC-4/' + name)
print('Release:', RELEASE)
print('ZIP:', ROOT / 'release' / 'ManagerPC-4.zip')
