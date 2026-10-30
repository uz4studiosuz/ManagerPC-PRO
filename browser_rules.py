"""Only modify the numbered URLBlocklist entries owned by ManagerPC."""
import json
from pathlib import Path
from secure_transport import atomic_json

PATHS = [r'SOFTWARE\Policies\Google\Chrome\URLBlocklist', r'SOFTWARE\Policies\Microsoft\Edge\URLBlocklist']


def apply(domains, base):
    import winreg
    manifest = Path(base) / 'browser-rules.json'
    owned = json.loads(manifest.read_text()) if manifest.exists() else {}
    domains = set(domains)
    if domains.intersection({'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}):
        domains.update({'youtube.com', 'youtu.be', 'youtube-nocookie.com'})
    for path in PATHS:
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY) as key:
            current = {}
            for n in range(winreg.QueryInfoKey(key)[1]):
                name, value, kind = winreg.EnumValue(key, n)
                current[name] = value
            entries = owned.setdefault(path, {})
            for name, value in list(entries.items()):
                if value not in domains:
                    if current.get(name) == value:
                        winreg.DeleteValue(key, name); current.pop(name, None)
                    entries.pop(name)
            atomic_json(manifest, owned)
            for domain in sorted(domains):
                if domain in current.values(): continue
                if len(current) >= 1000: raise ValueError('Brauzer blok ro‘yxati 1000 tadan oshdi')
                number = 1
                while str(number) in current: number += 1
                name = str(number)
                entries[name] = domain
                atomic_json(manifest, owned)  # Journal ownership before the registry mutation.
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, domain)
                current[name] = domain


def remove(base):
    apply([], base)
