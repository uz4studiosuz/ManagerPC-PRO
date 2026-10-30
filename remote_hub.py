"""Finite, authenticated actions. No shell, arbitrary commands, or file access."""
import base64
import collections
import math
import secrets
import time
from urllib.parse import urlsplit

SYSTEM_ACTIONS = {'restart', 'shutdown', 'cancel_shutdown', 'rescan'}
DESKTOP_ACTIONS = {'message', 'open_url', 'lock', 'focus', 'unfocus', 'input', 'text'}
KEYS = {'Enter', 'Tab', 'Escape', 'Backspace', 'Delete', 'Insert', 'Home', 'End', 'PageUp',
        'PageDown', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space', 'ShiftLeft',
        'ShiftRight', 'ControlLeft', 'ControlRight', 'AltLeft', 'AltRight', 'MetaLeft', 'MetaRight',
        'CapsLock', 'Minus', 'Equal', 'BracketLeft', 'BracketRight', 'Backslash', 'Semicolon',
        'Quote', 'Comma', 'Period', 'Slash', 'Backquote'}
KEYS |= {f'Key{chr(n)}' for n in range(65, 91)} | {f'Digit{n}' for n in range(10)} | {f'F{n}' for n in range(1, 13)}


def validate_action(kind, args):
    if kind not in SYSTEM_ACTIONS | DESKTOP_ACTIONS:
        raise ValueError('Bu amal qo‘llab-quvvatlanmaydi')
    if not isinstance(args, dict): raise ValueError('Amal parametrlari noto‘g‘ri')
    if kind in {'message', 'text'}:
        text = args.get('text')
        if not isinstance(text, str) or not 1 <= len(text) <= 2000: raise ValueError('Matn 1–2000 belgi bo‘lsin')
        return {'text': text}
    if kind == 'open_url':
        url = args.get('url', '')
        parsed = urlsplit(url)
        if len(url) > 2048 or parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username:
            raise ValueError('Faqat http yoki https sayt manzilini kiriting')
        return {'url': url}
    if kind == 'focus':
        seconds = args.get('seconds', 60)
        if not isinstance(seconds, int) or not 10 <= seconds <= 600: raise ValueError('Vaqt 10–600 soniya bo‘lsin')
        return {'seconds': seconds}
    if kind == 'input':
        event = args.get('event')
        if event in ('move', 'down', 'up', 'wheel'):
            result = {'event': event}
            for axis in ('x', 'y'):
                value = args.get(axis)
                if not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError('Ekran koordinatasi noto‘g‘ri')
                result[axis] = value
            if event in ('down', 'up'):
                if args.get('button') not in (0, 1, 2): raise ValueError('Sichqoncha tugmasi noto‘g‘ri')
                result['button'] = args['button']
            if event == 'wheel':
                if args.get('delta') not in (-120, 120): raise ValueError('Scroll qiymati noto‘g‘ri')
                result['delta'] = args['delta']
            return result
        if event in ('key_down', 'key_up') and args.get('code') in KEYS:
            return {'event': event, 'code': args['code']}
        raise ValueError('Klaviatura hodisasi noto‘g‘ri')
    return {}


class Hub:
    def __init__(self):
        self.desktops = {}
        self.leases = {}
        self.frames = {}
        self.pending = {}
        self.events = collections.deque(maxlen=250)

    def log(self, host, action, status, detail=''):
        self.events.appendleft({'time': time.time(), 'host': host, 'action': action,
                                'status': status, 'detail': str(detail)[:300]})

    def active(self, host):
        lease = self.leases.get(host, {})
        if lease.get('until', 0) <= time.time():
            self.frames.pop(host, None)
            return {'mode': 'idle', 'quality': 'grid'}
        return lease

    def lease(self, host, mode, quality='detail'):
        if mode not in {'idle', 'view', 'control'} or quality not in {'grid', 'detail'}:
            raise ValueError('Ekran rejimi noto‘g‘ri')
        old = self.active(host).get('mode')
        self.leases[host] = {'mode': mode, 'quality': quality, 'until': time.time() + (15 if mode != 'idle' else 0)}
        if old != mode: self.log(host, 'screen', mode)
        if mode != 'control':
            self.pending[host] = {k: v for k, v in self.pending.get(host, {}).items() if v['kind'] not in {'input', 'text'}}
        if mode == 'idle': self.frames.pop(host, None)

    def queue(self, host, kind, args):
        args = validate_action(kind, args)
        if kind in {'input', 'text'} and self.active(host).get('mode') != 'control':
            raise ValueError('Avval boshqaruv rejimini yoqing')
        desktop = self.desktops.get(host, {})
        if kind in DESKTOP_ACTIONS and (time.time() - desktop.get('time', 0) > 10 or desktop.get('paused')):
            raise ValueError('O‘quvchi sessiyasi ulanmagan yoki mahalliy pauza yoqilgan')
        jobs = self.pending.setdefault(host, {})
        self.prune(host)
        if kind == 'input' and args.get('event') == 'move':
            for key, job in list(jobs.items()):
                if job['kind'] == 'input' and job['args'].get('event') == 'move': del jobs[key]
        if len(jobs) >= 100: raise ValueError('Buyruqlar navbati to‘ldi, biroz kuting')
        command = {'id': secrets.token_hex(12), 'kind': kind, 'args': args,
                   'expires': time.time() + (4 if kind == 'input' else 30)}
        jobs[command['id']] = command
        if kind != 'input': self.log(host, kind, 'queued')
        return command['id']

    def prune(self, host):
        for key, job in list(self.pending.get(host, {}).items()):
            if job['expires'] < time.time():
                if job['kind'] != 'input': self.log(host, job['kind'], 'expired')
                del self.pending[host][key]

    def commands(self, host, role, acknowledgements):
        allowed = SYSTEM_ACTIONS if role == 'agent' else DESKTOP_ACTIONS
        jobs = self.pending.setdefault(host, {})
        if isinstance(acknowledgements, list):
            for ack in acknowledgements[:100]:
                if not isinstance(ack, dict): continue
                job = jobs.get(ack.get('id'))
                if job and job['kind'] in allowed:
                    if job['kind'] != 'input' or not ack.get('ok'):
                        self.log(host, job['kind'], 'done' if ack.get('ok') else 'failed', ack.get('error', ''))
                    del jobs[job['id']]
        self.prune(host)
        return [v for v in jobs.values() if v['kind'] in allowed][:40]

    def frame(self, host, body):
        if self.active(host).get('mode') == 'idle': return
        value = body.get('frame')
        if not isinstance(value, str) or len(value) > 1400000: raise ValueError('Ekran tasviri juda katta')
        raw = base64.b64decode(value, validate=True)
        if not raw.startswith(b'\xff\xd8') or not raw.endswith(b'\xff\xd9'): raise ValueError('JPEG tasviri kerak')
        self.frames[host] = {'data': raw, 'time': time.time()}

    def snapshot(self):
        now = time.time()
        for host in list(self.frames):
            if self.active(host).get('mode') == 'idle' or now - self.frames.get(host, {}).get('time', 0) > 10:
                self.frames.pop(host, None)
        return {host: {**value, 'online': now - value['time'] < 10,
                       'mode': self.active(host).get('mode'), 'frame_time': self.frames.get(host, {}).get('time', 0)}
                for host, value in self.desktops.items()}
