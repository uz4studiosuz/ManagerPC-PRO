import csv
import hashlib
import io
import ipaddress
import json
import os
import re
import secrets
import socket
import ssl
import sys
import threading
import time
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from remote_hub import Hub, SYSTEM_ACTIONS
from secure_transport import atomic_json, make_certificate

ROOT = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
DATA = Path(os.getenv('LOCALAPPDATA', str(ROOT))) / 'ManagerPC'
DATA.mkdir(parents=True, exist_ok=True)
FILE = DATA / 'settings.json'
state = json.loads(FILE.read_text(encoding='utf-8')) if FILE.exists() else {}
state.setdefault('global', {'domains': [], 'apps': []})
state.setdefault('pcs', {})
state.setdefault('devices', {})
state.setdefault('packages', {})
lock = threading.RLock()
seen = {}
hub = Hub()
CSRF = secrets.token_urlsafe(32)
CERT = None
HOST = re.compile(r'[A-Z0-9][A-Z0-9-]{0,62}\Z')
PROTECTED = {'managerpc-agent.exe', 'managerpc-desktop.exe', 'system.exe', 'csrss.exe', 'lsass.exe',
    'services.exe', 'smss.exe', 'wininit.exe', 'winlogon.exe', 'svchost.exe', 'explorer.exe', 'taskhostw.exe', 'dwm.exe'}


def save(): atomic_json(FILE, state)


def app_name(name):
    return isinstance(name, str) and 4 < len(name) <= 180 and name.lower().endswith('.exe') and not any(c in name for c in '/\\:*?"<>|\r\n') and name.lower() not in PROTECTED


def clean_policy(value):
    if not isinstance(value, dict): raise ValueError('Qoida noto‘g‘ri')
    result = {'domains': [], 'apps': []}
    for key in result:
        items = value.get(key, [])
        if not isinstance(items, list) or len(items) > 1000: raise ValueError('Ro‘yxat 1000 tadan oshmasin')
        for item in items:
            if not isinstance(item, str): raise ValueError('Matn kiriting')
            item = item.strip().lower()
            if key == 'apps':
                if not app_name(item): raise ValueError('Dastur nomi noto‘g‘ri yoki himoyalangan: ' + item)
            else:
                item = re.sub(r'^https?://', '', item).split('/')[0].rstrip('.')
                if len(item) > 253 or '.' not in item or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', x) for x in item.split('.')):
                    raise ValueError('Domen noto‘g‘ri: ' + item)
            result[key].append(item)
        result[key] = sorted(set(result[key]))
    return result


def host_name(value):
    host = str(value).upper()
    if not HOST.fullmatch(host): raise ValueError('Hostname noto‘g‘ri')
    return host


def digest(token): return hashlib.sha256(str(token).encode()).hexdigest()


def authenticate(body, role):
    device = state['devices'].get(str(body.get('id', '')))
    if not device or not secrets.compare_digest(device.get(role, ''), digest(body.get('token', ''))):
        raise PermissionError('Agent kaliti noto‘g‘ri yoki bekor qilingan')
    return device['host']


def enroll(body):
    package = state['packages'].get(digest(body.get('package', '')))
    if not package or package['expires'] < time.time(): raise PermissionError('O‘rnatish paketi eskirgan. Paneldan yangisini oling.')
    host = host_name(body.get('hostname', ''))
    old = state['devices'].get(body.get('id', ''))
    if old and old['host'] == host and secrets.compare_digest(old['agent'], digest(body.get('token', ''))):
        desktop_token = secrets.token_urlsafe(32)
        old['desktop'] = digest(desktop_token)
        save()
        return {'id': body['id'], 'token': body['token'], 'desktop_token': desktop_token}
    if any(d['host'] == host for d in state['devices'].values()):
        raise ValueError('Bu hostname ulangan. Panelda eski ulanishni bekor qiling yoki boshqa hostname ishlating.')
    identifier, token, desktop_token = secrets.token_hex(16), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    state['devices'][identifier] = {'host': host, 'agent': digest(token), 'desktop': digest(desktop_token)}
    state['pcs'].setdefault(host, {'domains': [], 'apps': []})
    save(); hub.log(host, 'enroll', 'done')
    return {'id': identifier, 'token': token, 'desktop_token': desktop_token}


def package_bytes(address):
    if not isinstance(address, str): raise ValueError('Admin IPv4 yoki hostname kiriting')
    address = str(address).strip()
    try: ipaddress.IPv4Address(address)
    except ValueError:
        if not HOST.fullmatch(address.upper()): raise ValueError('Admin IPv4 yoki hostname kiriting')
    files = ['ManagerPC-Agent.exe', 'ManagerPC-Desktop.exe', 'install-agent.ps1', 'AGENT-INSTALL.bat',
             'remove-agent.ps1', 'AGENT-REMOVE.bat']
    if not all((ROOT / f).is_file() for f in files): raise ValueError('Agent EXE yoki o‘rnatish fayllari topilmadi')
    token = secrets.token_urlsafe(32)
    state['packages'] = {key: value for key, value in state['packages'].items() if value['expires'] > time.time()}
    state['packages'][digest(token)] = {'expires': time.time() + 8 * 3600}
    save()
    cert_path, _, fingerprint = CERT
    info = {'server': 'https://' + address + ':8766', 'package': token, 'fingerprint': fingerprint}
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in files: archive.write(ROOT / name, name)
        archive.write(cert_path, 'server-cert.pem')
        archive.writestr('enrollment.json', json.dumps(info))
        archive.writestr('BOSHLASH.txt', '1. ZIP ni alohida papkaga chiqaring.\n2. AGENT-INSTALL.bat ni administrator sifatida oching.\n3. Windows hisobidan chiqib qayta kiring.\nPaket 8 soat amal qiladi.\n')
    return output.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def setup(self):
        super().setup(); self.connection.settimeout(12)

    def reply(self, code, obj, kind='application/json; charset=utf-8', filename=None):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        if filename: self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError): pass

    def local(self):
        port = self.server.server_port
        return (not getattr(self.server, 'agent_listener', False)
                and self.client_address[0] in ('127.0.0.1', '::1')
                and self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}'))

    def admin_write(self):
        port = self.server.server_port
        return (self.local() and self.headers.get('Origin') in (f'http://127.0.0.1:{port}', f'http://localhost:{port}')
                and secrets.compare_digest(self.headers.get('X-ManagerPC', ''), CSRF))

    def do_GET(self):
        if not self.local(): return self.reply(403, {'error': 'Admin panel faqat shu kompyuterda ochiladi'})
        parsed = urlsplit(self.path)
        if parsed.path in ('/', '/app.js', '/style.css'):
            name, mime = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}[parsed.path]
            return self.reply(200, (ROOT / name).read_bytes(), mime)
        with lock:
            if parsed.path == '/api/state':
                for host in list(hub.pending): hub.prune(host)
                now = time.time()
                return self.reply(200, {'version': '4.0', 'csrf': CSRF, 'global': state['global'], 'pcs': state['pcs'],
                    'seen': {k: dict(v, online=now-v['time'] < 30) for k, v in seen.items()},
                    'desktop': hub.snapshot(), 'events': list(hub.events), 'server': socket.gethostname(),
                    'enrolled': [d['host'] for d in state['devices'].values()]})
            if parsed.path == '/api/frame':
                host = parse_qs(parsed.query).get('host', [''])[0]
                hub.snapshot()
                frame = hub.frames.get(host)
                if not frame: return self.reply(404, {'error': 'Yangi ekran tasviri yo‘q'})
                return self.reply(200, frame['data'], 'image/jpeg')
            if parsed.path == '/api/backup':
                return self.reply(200, json.dumps({'format': 1, 'global': state['global'], 'pcs': state['pcs']}, ensure_ascii=False, indent=2).encode(), filename='ManagerPC-qoidalar.json')
        return self.reply(404, {'error': 'Topilmadi'})

    def do_POST(self):
        try:
            is_agent = getattr(self.server, 'agent_listener', False)
            if not is_agent and not self.admin_write(): raise PermissionError('Admin so‘rovi tasdiqlanmadi. Sahifani yangilang.')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json': raise ValueError('JSON kerak')
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 2 * 1024 * 1024: raise ValueError('So‘rov hajmi noto‘g‘ri')
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict): raise ValueError('So‘rov noto‘g‘ri')
            with lock:
                if is_agent: return self.agent_post(body)
                return self.admin_post(body)
        except PermissionError as exc: self.reply(403, {'error': str(exc)})
        except (ValueError, TypeError, KeyError) as exc: self.reply(400, {'error': str(exc)})
        except OSError as exc: self.reply(500, {'error': 'Fayl yoki tarmoq xatosi: ' + str(exc)})

    def agent_post(self, body):
        if self.path == '/agent/enroll': return self.reply(200, enroll(body))
        if self.path == '/agent/heartbeat':
            host = authenticate(body, 'agent')
            inv = body.get('inventory', {})
            if not isinstance(inv, dict): inv = {}
            inventory = {key: [n for n in (inv.get(key) if isinstance(inv.get(key), list) else [])[:1000] if app_name(n)] for key in ('installed', 'running')}
            system = body.get('system', {})
            if not isinstance(system, dict): system = {}
            seen[host] = {'time': time.time(), 'ip': self.client_address[0], 'inventory': inventory,
                'error': str(body.get('error', ''))[:500], 'version': str(body.get('version', ''))[:20],
                'system': {k: str(system.get(k, ''))[:200] for k in ('os', 'cpu', 'ram', 'disk_free', 'uptime')},
                'applied': str(body.get('applied', ''))[:64]}
            pc = state['pcs'].get(host, {})
            policy = {key: sorted(set(state['global'][key] + pc.get(key, []))) for key in ('domains', 'apps')}
            return self.reply(200, {'policy': policy, 'commands': hub.commands(host, 'agent', body.get('results', []))})
        if self.path == '/desktop/poll':
            host = authenticate(body, 'desktop')
            paused = bool(body.get('paused'))
            windows = body.get('windows', [])
            if not isinstance(windows, list): windows = []
            hub.desktops[host] = {'time': time.time(), 'paused': paused, 'user': str(body.get('user', ''))[:80],
                'error': str(body.get('error', ''))[:300],
                'windows': [{'name': str(w.get('name', ''))[:180], 'title': str(w.get('title', ''))[:200]}
                            for w in windows[:100] if isinstance(w, dict)]}
            if paused:
                hub.lease(host, 'idle'); hub.frames.pop(host, None)
            elif body.get('frame'): hub.frame(host, body)
            commands = hub.commands(host, 'desktop', body.get('results', []))
            return self.reply(200, {'session': hub.active(host), 'commands': commands, 'server_time': time.time()})
        return self.reply(404, {'error': 'Agent amali topilmadi'})

    def admin_post(self, body):
        if self.path == '/api/package':
            return self.reply(200, package_bytes(body.get('address')), 'application/zip', 'ManagerPC-Oquvchi.zip')
        if self.path == '/api/policy':
            host = '*' if body.get('host') == '*' else host_name(body.get('host'))
            policy = clean_policy(body.get('policy'))
            if host == '*': state['global'] = policy
            else: state['pcs'][host] = policy
            save(); hub.log(host, 'policy', 'saved')
            return self.reply(200, {'ok': True})
        if self.path == '/api/delete':
            host = host_name(body.get('host'))
            state['pcs'].pop(host, None); save()
            return self.reply(200, {'ok': True})
        if self.path == '/api/restore':
            backup = body.get('backup', {})
            if not isinstance(backup, dict) or backup.get('format') != 1 or not isinstance(backup.get('pcs'), dict) or len(backup['pcs']) > 500:
                raise ValueError('Zaxira fayli noto‘g‘ri')
            global_policy = clean_policy(backup.get('global'))
            pcs = {host_name(host): clean_policy(policy) for host, policy in backup['pcs'].items()}
            state['global'], state['pcs'] = global_policy, pcs
            save(); hub.log('*', 'restore', 'done')
            return self.reply(200, {'ok': True})
        host = host_name(body.get('host'))
        if host not in state['pcs'] and host not in seen: raise ValueError('Kompyuter topilmadi')
        if self.path == '/api/session':
            if host not in hub.desktops or time.time() - hub.desktops[host]['time'] > 10:
                raise ValueError('O‘quvchi Windows hisobiga kirmagan yoki Desktop yordamchisi ishlamayapti')
            if hub.desktops[host]['paused'] and body.get('mode') != 'idle': raise ValueError('O‘quvchi kompyuterida mahalliy pauza yoqilgan')
            hub.lease(host, body.get('mode'), body.get('quality', 'detail'))
            return self.reply(200, {'ok': True})
        if self.path == '/api/action':
            kind = body.get('kind')
            if kind in SYSTEM_ACTIONS and time.time() - seen.get(host, {}).get('time', 0) > 30:
                raise ValueError('Kompyuter oflayn')
            return self.reply(200, {'id': hub.queue(host, kind, body.get('args', {}))})
        if self.path == '/api/revoke':
            state['devices'] = {k: v for k, v in state['devices'].items() if v['host'] != host}
            hub.lease(host, 'idle'); hub.desktops.pop(host, None); hub.pending.pop(host, None)
            save(); hub.log(host, 'revoke', 'done')
            return self.reply(200, {'ok': True})
        return self.reply(404, {'error': 'Amal topilmadi'})


def main():
    global CERT
    CERT = make_certificate(DATA)
    agent_server = ThreadingHTTPServer(('0.0.0.0', 8766), Handler)
    agent_server.agent_listener = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(CERT[0]), str(CERT[1]))
    agent_server.socket = context.wrap_socket(agent_server.socket, server_side=True, do_handshake_on_connect=False)
    admin_server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    threading.Thread(target=agent_server.serve_forever, daemon=True).start()
    print('ManagerPC 4 — http://127.0.0.1:8765\nAgentlar uchun xavfsiz port: TCP 8766', flush=True)
    threading.Timer(1, lambda: webbrowser.open('http://127.0.0.1:8765')).start()
    try: admin_server.serve_forever()
    finally: agent_server.shutdown(); agent_server.server_close(); admin_server.server_close()


if __name__ == '__main__':
    try:
        if '--self-test' in sys.argv:
            cert, key, _ = make_certificate(DATA)
            ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(str(cert), str(key))
        else: main()
    except OSError as exc:
        print('ManagerPC ishga tushmadi. Eski admin oynasini yoping va qayta urinib ko‘ring.\n' + str(exc), flush=True)
        sys.exit(1)
