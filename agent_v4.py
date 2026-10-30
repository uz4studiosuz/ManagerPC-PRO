import collections
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
from agent import scan_apps, update_hosts
from secure_transport import request, atomic_json
import browser_rules

BASE = Path(os.environ.get('PROGRAMDATA', '.')) / 'ManagerPC-Agent'
CONFIG = BASE / 'service' / 'config.json'
PROTECTED = {'managerpc-agent.exe', 'managerpc-desktop.exe', 'system', 'system idle process', 'csrss.exe', 'lsass.exe',
             'services.exe', 'smss.exe', 'wininit.exe', 'winlogon.exe', 'svchost.exe', 'explorer.exe', 'taskhostw.exe', 'dwm.exe'}


def enroll(package_dir):
    directory = Path(package_dir)
    enrollment = json.loads((directory / 'enrollment.json').read_text(encoding='utf-8-sig'))
    enrollment['certificate'] = str(directory / 'server-cert.pem')
    previous = {}
    if CONFIG.exists(): previous = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    body = {'package': enrollment['package'], 'hostname': socket.gethostname(),
            'id': previous.get('id'), 'token': previous.get('token')}
    result = request(enrollment, '/agent/enroll', body)
    BASE.mkdir(parents=True, exist_ok=True)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    (BASE / 'server-cert.pem').write_bytes((directory / 'server-cert.pem').read_bytes())
    common = {'server': enrollment['server'], 'fingerprint': enrollment['fingerprint'],
              'certificate': str(BASE / 'server-cert.pem'), 'id': result['id']}
    atomic_json(CONFIG, dict(common, token=result['token']))
    atomic_json(BASE / 'desktop.json', dict(common, token=result['desktop_token']))


def run():
    config = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    policy_file = BASE / 'policy.json'
    try: policy = json.loads(policy_file.read_text())
    except (OSError, ValueError): policy = {'domains': [], 'apps': []}
    shared = {'policy': policy, 'installed': [], 'applied': '', 'error': ''}
    rescan = threading.Event()
    def scan_loop():
        while True:
            try: shared['installed'] = scan_apps()
            except Exception as exc: shared['error'] = 'Ro‘yxat: ' + str(exc)
            rescan.wait(180); rescan.clear()
    def enforce():
        last = None
        while True:
            try:
                current = shared['policy']
                revision = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
                if last != revision:
                    update_hosts(current['domains'])
                    browser_rules.apply(current['domains'], BASE)
                    last = revision; shared['applied'] = revision
                blocked = {n.lower() for n in current['apps']} - PROTECTED
                for proc in psutil.process_iter(['name']):
                    try:
                        if (proc.info['name'] or '').lower() in blocked: proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied): pass
                shared['error'] = ''
            except Exception as exc:
                shared['error'] = str(exc)[:500]
            time.sleep(2)
    threading.Thread(target=scan_loop, daemon=True).start()
    threading.Thread(target=enforce, daemon=True).start()
    completed = collections.OrderedDict()
    results = []
    while True:
        try:
            running = sorted({p.info['name'] for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() not in PROTECTED})[:1000]
            system = {'os': platform.platform(), 'cpu': str(psutil.cpu_count()) + ' yadro',
                      'ram': str(round(psutil.virtual_memory().total / 1024**3, 1)) + ' GB',
                      'disk_free': str(round(psutil.disk_usage(os.environ.get('SystemDrive', 'C:') + '/').free / 1024**3, 1)) + ' GB',
                      'uptime': str(int(time.time() - psutil.boot_time()))}
            body = {'id': config['id'], 'token': config['token'], 'version': '4.0', 'results': results,
                    'inventory': {'running': running, 'installed': shared['installed']}, 'system': system,
                    'applied': shared['applied'], 'error': shared['error']}
            response = request(config, '/agent/heartbeat', body)
            results = []
            if response['policy'] != shared['policy']:
                atomic_json(policy_file, response['policy']); shared['policy'] = response['policy']
            for command in response['commands']:
                identifier = command['id']
                if identifier not in completed:
                    result = {'id': identifier, 'ok': True}
                    try:
                        kind = command['kind']
                        if kind == 'rescan': rescan.set()
                        elif kind in ('restart', 'shutdown', 'cancel_shutdown'):
                            args = ['/a'] if kind == 'cancel_shutdown' else ['/r' if kind == 'restart' else '/s', '/t', '30', '/c', 'ManagerPC: oqituvchi buyrugi']
                            output = subprocess.run(['shutdown.exe', *args], capture_output=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW)
                            if output.returncode: raise ValueError(output.stderr.decode('mbcs', errors='replace')[:200])
                        else: raise ValueError('Amal qo‘llab-quvvatlanmaydi')
                    except Exception as exc: result.update(ok=False, error=str(exc)[:300])
                    completed[identifier] = result
                    if len(completed) > 500: completed.popitem(last=False)
                results.append(completed[identifier])
        except Exception as exc:
            (BASE / 'last-error.txt').write_text(str(exc)[:1000], encoding='utf-8')
        time.sleep(3)


if __name__ == '__main__':
    try:
        if '--self-test' in sys.argv:
            import winreg
            assert psutil.cpu_count() is not None
        elif len(sys.argv) > 2 and sys.argv[1] == '--enroll': enroll(sys.argv[2])
        elif len(sys.argv) > 1 and sys.argv[1] == '--remove-browser-rules': browser_rules.remove(BASE)
        else: run()
    except Exception as exc:
        BASE.mkdir(parents=True, exist_ok=True)
        (BASE / 'install-error.txt').write_text(str(exc), encoding='utf-8')
        sys.exit(1)
