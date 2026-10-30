import csv, ctypes, io, json, os, re, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

BASE = Path(os.environ.get('PROGRAMDATA', '.')) / 'ManagerPC-Agent'
CONFIG = BASE / 'config.json'
HOSTS = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/drivers/etc/hosts'
START = '# ManagerPC BEGIN'
END = '# ManagerPC END'
PROTECTED = {'managerpc-agent.exe', 'system.exe', 'system', 'idle', 'csrss.exe', 'lsass.exe', 'services.exe', 'smss.exe', 'wininit.exe', 'winlogon.exe', 'svchost.exe', 'explorer.exe', 'taskhostw.exe', 'dwm.exe'}

def app_name(name):
    return isinstance(name, str) and len(name) <= 180 and name.lower().endswith('.exe') and not any(c in name for c in '/\\:*?"<>|\r\n') and name.lower() not in PROTECTED

def running_apps():
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, timeout=20)
    output = result.stdout.decode('mbcs', errors='replace')
    return sorted({row[0] for row in csv.reader(io.StringIO(output)) if row and app_name(row[0])}, key=str.casefold)[:500]

def scan_apps():
    # Common installation and download folders; avoid walking Windows or entire drives.
    roots = [Path(os.environ.get('ProgramFiles', '')), Path(os.environ.get('ProgramFiles(x86)', ''))]
    users = Path(os.environ.get('SystemDrive', 'C:') + '/Users')
    if users.is_dir():
        for profile in users.iterdir():
            roots += [profile / 'AppData/Local/Programs', profile / 'AppData/Local', profile / 'Desktop', profile / 'Downloads']
    found = set()
    for root in roots:
        if not root.is_dir(): continue
        for folder, dirs, files in os.walk(root, followlinks=False):
            depth = len(Path(folder).relative_to(root).parts)
            dirs[:] = [d for d in dirs if d.lower() not in {'cache', 'caches', 'temp', 'packages', 'microsoft', 'windows', 'node_modules'} and depth < 5]
            for name in files:
                if app_name(name): found.add(name)
            if len(found) >= 1000: return sorted(found, key=str.casefold)[:1000]
    return sorted(found, key=str.casefold)

def update_hosts(domains):
    original = HOSTS.read_text(encoding='utf-8', errors='surrogateescape') if HOSTS.exists() else ''
    # Refuse ambiguous or damaged markers instead of deleting unrelated content.
    if original.count(START) != original.count(END) or original.count(START) > 1: raise ValueError('hosts faylidagi ManagerPC belgilari buzilgan')
    if START in original:
        a, b = original.index(START), original.index(END)
        if b < a: raise ValueError('hosts belgilari noto‘g‘ri tartibda')
        original = original[:a].rstrip('\r\n') + original[b+len(END):]
    original = original.rstrip('\r\n')
    lines = []
    domains = set(domains)
    if domains.intersection({'youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com'}):
        domains.update({'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'youtube-nocookie.com', 'www.youtube-nocookie.com'})
    for domain in sorted(domains):
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', domain): raise ValueError('Noto‘g‘ri domen')
        for name in dict.fromkeys([domain, 'www.' + domain if not domain.startswith('www.') else domain]):
            lines.extend(['0.0.0.0 ' + name, ':: ' + name])
    result = original + ('\n' if original else '') + START + '\n' + '\n'.join(lines) + ('\n' if lines else '') + END + '\n'
    current = HOSTS.read_text(encoding='utf-8', errors='surrogateescape') if HOSTS.exists() else ''
    if result != current:
        HOSTS.write_text(result, encoding='utf-8', errors='surrogateescape')
        subprocess.run(['ipconfig', '/flushdns'], capture_output=True, timeout=10)

def main():
    config = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    error = ''
    cache = BASE / 'policy.json'
    try: policy = json.loads(cache.read_text(encoding='utf-8'))
    except (OSError, ValueError): policy = None
    inventory = {'installed': [], 'running': []}
    def scan_loop():
        while True:
            try: inventory['installed'] = scan_apps()
            except (OSError, ValueError): pass
            time.sleep(180)
    threading.Thread(target=scan_loop, daemon=True).start()
    while True:
        try:
            if os.name == 'nt':
                ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
                uptime = int(ctypes.windll.kernel32.GetTickCount64() // 1000)
            else: uptime = 0
            try: inventory['running'] = running_apps()
            except Exception: pass
            payload = json.dumps({'token':config['token'], 'hostname':socket.gethostname(), 'error':error, 'uptime':uptime, 'version':'1.2', 'inventory':inventory}).encode()
            request = urllib.request.Request(config['server'].rstrip('/') + '/api/heartbeat', data=payload, headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request, timeout=8) as response: policy = json.load(response)
            cache.write_text(json.dumps(policy), encoding='utf-8')
            error = ''
        except Exception as exc:
            error = str(exc)[:500]
            BASE.mkdir(parents=True, exist_ok=True)
            (BASE / 'last-error.txt').write_text(error, encoding='utf-8')
        try:
            if policy is None:
                time.sleep(10)
                continue
            update_hosts(policy['domains'])
            for app in policy['apps']:
                if app_name(app): subprocess.run(['taskkill', '/F', '/IM', app], capture_output=True, timeout=10)
        except Exception as exc:
            error = str(exc)[:500]
            BASE.mkdir(parents=True, exist_ok=True)
            (BASE / 'last-error.txt').write_text(error, encoding='utf-8')
        time.sleep(10)

if __name__ == '__main__': main()
