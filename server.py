import json, os, re, secrets, shutil, socket, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
DATA = Path(os.getenv('LOCALAPPDATA', str(ROOT))) / 'ManagerPC'
DATA.mkdir(parents=True, exist_ok=True)
FILE = DATA / 'settings.json'
lock = threading.RLock()

def load():
    if FILE.exists():
        return json.loads(FILE.read_text(encoding='utf-8'))
    return {'token': secrets.token_urlsafe(24), 'global': {'domains': [], 'apps': []}, 'pcs': {}}

state = load()
seen = {}
PROTECTED = {'managerpc-agent.exe', 'system.exe', 'csrss.exe', 'lsass.exe', 'services.exe', 'smss.exe', 'wininit.exe', 'winlogon.exe', 'svchost.exe', 'explorer.exe', 'taskhostw.exe', 'dwm.exe'}

def app_name(name):
    return isinstance(name, str) and len(name) <= 180 and name.lower().endswith('.exe') and not any(c in name for c in '/\\:*?"<>|\r\n') and name.lower() not in PROTECTED

def veyon_program(name):
    for directory in (os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')):
        if directory:
            candidate = Path(directory) / 'Veyon' / name
            if candidate.is_file(): return str(candidate)
    return shutil.which(name)

def launch_veyon(mode, host=None):
    if mode == 'master':
        executable = veyon_program('veyon-master.exe')
        args = []
    elif mode in ('view', 'control'):
        if not isinstance(host, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9-]{0,62}', host):
            raise ValueError('Kompyuter nomi noto‘g‘ri')
        if host not in state['pcs'] and host not in seen: raise ValueError('Kompyuter ro‘yxatda topilmadi')
        executable = veyon_program('veyon-wcli.exe') or veyon_program('veyon-cli.exe')
        args = ['remoteaccess', mode, host]
    else: raise ValueError('Noto‘g‘ri amal')
    if not executable: raise ValueError('Veyon admin kompyuterida topilmadi. Uni o‘rnating va sozlang.')
    try: subprocess.Popen([executable, *args], cwd=str(Path(executable).parent))
    except OSError as exc: raise ValueError('Veyon ishga tushmadi: ' + str(exc)) from exc

def save():
    tmp = FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, FILE)

save()

def clean_policy(value):
    if not isinstance(value, dict): raise ValueError('Noto‘g‘ri ma’lumot')
    domains, apps = [], []
    for item in value.get('domains', []):
        item = item.strip().lower().rstrip('.')
        item = re.sub(r'^https?://', '', item).split('/')[0].split(':')[0]
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', item) or '.' not in item or '..' in item:
            raise ValueError('Sayt manzili noto‘g‘ri: ' + item)
        domains.append(item)
    for item in value.get('apps', []):
        item = item.strip().lower()
        if not app_name(item): raise ValueError('Dastur nomi noto‘g‘ri yoki tizim uchun himoyalangan: ' + item)
        apps.append(item)
    return {'domains': sorted(set(domains)), 'apps': sorted(set(apps))}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, code, obj, kind='application/json; charset=utf-8'):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type', kind); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)
    def local(self): return self.client_address[0] in ('127.0.0.1', '::1')
    def do_GET(self):
        if not self.local(): return self.reply(403, {'error': 'Faqat admin kompyuterida'})
        if self.path == '/': return self.reply(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if self.path == '/api/state':
            with lock:
                now = time.time()
                return self.reply(200, {'token': state['token'], 'global': state['global'], 'pcs': state['pcs'], 'seen': {k: dict(v, online=now-v['time'] < 45) for k,v in seen.items()}, 'server': socket.gethostname(), 'veyon': bool(veyon_program('veyon-wcli.exe') or veyon_program('veyon-cli.exe'))})
        self.reply(404, {})
    def do_POST(self):
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json': raise ValueError('JSON talab qilinadi')
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 524288: raise ValueError('Ma’lumot hajmi noto‘g‘ri')
            body = json.loads(self.rfile.read(size))
            with lock:
                if self.path == '/api/heartbeat':
                    if not secrets.compare_digest(str(body.get('token', '')), state['token']): return self.reply(403, {'error':'Kalit noto‘g‘ri'})
                    host = str(body.get('hostname', '')).upper()
                    if not re.fullmatch(r'[A-Z0-9][A-Z0-9-]{0,62}', host): raise ValueError('Hostname noto‘g‘ri')
                    uptime = body.get('uptime', 0)
                    if not isinstance(uptime, int) or uptime < 0: uptime = 0
                    inv = body.get('inventory', {})
                    if not isinstance(inv, dict): inv = {}
                    inventory = {key: [name for name in (inv.get(key) if isinstance(inv.get(key), list) else [])[:1000] if app_name(name)] for key in ('installed', 'running')}
                    seen[host] = {'time': time.time(), 'ip': self.client_address[0], 'error': str(body.get('error', ''))[:500], 'uptime': uptime, 'version': str(body.get('version', ''))[:20], 'inventory': inventory}
                    global_policy = state['global']; pc = state['pcs'].get(host, {})
                    return self.reply(200, {'domains': sorted(set(global_policy['domains'] + pc.get('domains', []))), 'apps': sorted(set(global_policy['apps'] + pc.get('apps', [])))})
                if not self.local(): return self.reply(403, {'error':'Faqat admin kompyuterida'})
                origin = self.headers.get('Origin', '')
                if origin not in ('http://127.0.0.1:8765', 'http://localhost:8765'): return self.reply(403, {'error':'Origin noto‘g‘ri'})
                if self.path == '/api/policy':
                    host = str(body.get('host', '')).upper()
                    policy = clean_policy(body.get('policy'))
                    if host == '*': state['global'] = policy
                    elif re.fullmatch(r'[A-Z0-9][A-Z0-9-]{0,62}', host): state['pcs'][host] = policy
                    else: raise ValueError('Hostname noto‘g‘ri')
                    save(); return self.reply(200, {'ok': True})
                if self.path == '/api/delete':
                    state['pcs'].pop(str(body.get('host', '')).upper(), None); save(); return self.reply(200, {'ok':True})
                if self.path == '/api/remote':
                    launch_veyon(body.get('mode'), str(body.get('host', '')).upper())
                    return self.reply(200, {'ok': True})
            self.reply(404, {})
        except (ValueError, TypeError, json.JSONDecodeError) as exc: self.reply(400, {'error': str(exc)})

if __name__ == '__main__':
    print('ManagerPC admin panel: http://127.0.0.1:8765', flush=True)
    threading.Timer(1, lambda: webbrowser.open('http://127.0.0.1:8765')).start()
    ThreadingHTTPServer(('0.0.0.0', 8765), Handler).serve_forever()
