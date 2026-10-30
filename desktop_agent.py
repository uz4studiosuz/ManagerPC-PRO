"""Runs in the logged-in student's session, never as the SYSTEM service."""
import base64
import collections
import ctypes
from ctypes import wintypes
import getpass
import io
import json
import os
import sys
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
import webbrowser

import psutil
from PIL import Image, ImageGrab
from remote_hub import validate_action
from secure_transport import request

BASE = Path(os.environ.get('PROGRAMDATA', '.')) / 'ManagerPC-Agent'


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]


class INPUTUNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('type', wintypes.DWORD), ('data', INPUTUNION)]


KEYMAP = {'Enter': 13, 'Tab': 9, 'Escape': 27, 'Backspace': 8, 'Delete': 46, 'Insert': 45, 'Home': 36,
          'End': 35, 'PageUp': 33, 'PageDown': 34, 'ArrowUp': 38, 'ArrowDown': 40, 'ArrowLeft': 37,
          'ArrowRight': 39, 'Space': 32, 'ShiftLeft': 160, 'ShiftRight': 161, 'ControlLeft': 162,
          'ControlRight': 163, 'AltLeft': 164, 'AltRight': 165, 'MetaLeft': 91, 'MetaRight': 92,
          'CapsLock': 20, 'Minus': 189, 'Equal': 187, 'BracketLeft': 219, 'BracketRight': 221,
          'Backslash': 220, 'Semicolon': 186, 'Quote': 222, 'Comma': 188, 'Period': 190,
          'Slash': 191, 'Backquote': 192}
KEYMAP.update({f'Key{chr(n)}': n for n in range(65, 91)})
KEYMAP.update({f'Digit{n}': 48+n for n in range(10)})
KEYMAP.update({f'F{n}': 111+n for n in range(1, 13)})
EXTENDED = {'Delete', 'Insert', 'Home', 'End', 'PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ControlRight', 'AltRight', 'MetaLeft', 'MetaRight'}


def available_desktop():
    kernel, user = ctypes.windll.kernel32, ctypes.windll.user32
    session = wintypes.DWORD()
    kernel.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
    if session.value != kernel.WTSGetActiveConsoleSessionId(): return False
    user.OpenInputDesktop.restype = wintypes.HANDLE
    handle = user.OpenInputDesktop(0, False, 1)
    if not handle: return False
    try:
        buf = ctypes.create_unicode_buffer(256)
        required = wintypes.DWORD()
        user.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        return bool(user.GetUserObjectInformationW(handle, 2, buf, ctypes.sizeof(buf), ctypes.byref(required))) and buf.value.lower() == 'default'
    finally:
        user.CloseDesktop.argtypes = [wintypes.HANDLE]
        user.CloseDesktop(handle)


def open_windows():
    import win32gui
    import win32process
    found = []
    def visit(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd): return
        title = win32gui.GetWindowText(hwnd)
        if not title or title.startswith('ManagerPC'): return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            name = psutil.Process(pid).name()
            found.append({'name': name, 'title': title[:200]})
        except (psutil.Error, OSError): pass
    win32gui.EnumWindows(visit, None)
    return found[:100]


class InputController:
    def __init__(self):
        self.keys, self.buttons = set(), set()
        self.user = ctypes.windll.user32
        self.user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        self.user.SendInput.restype = wintypes.UINT

    def send(self, entries):
        array = (INPUT * len(entries))(*entries)
        if self.user.SendInput(len(entries), array, ctypes.sizeof(INPUT)) != len(entries):
            raise ValueError('Windows kiritishni rad etdi: UAC yoki himoyalangan oyna bo‘lishi mumkin')

    def key(self, code, up=False):
        flags = (2 if up else 0) | (1 if code in EXTENDED else 0)
        self.send([INPUT(type=1, ki=KEYBDINPUT(KEYMAP[code], 0, flags, 0, 0))])
        if up: self.keys.discard(code)
        else: self.keys.add(code)

    def event(self, args):
        event = args['event']
        if event in ('key_down', 'key_up'): return self.key(args['code'], event == 'key_up')
        flags, data = 0x8000 | 1, 0
        if event in ('down', 'up'):
            flags |= {0: (2, 4), 1: (32, 64), 2: (8, 16)}[args['button']][event == 'up']
        elif event == 'wheel': flags |= 0x0800; data = args['delta'] & 0xffffffff
        self.send([INPUT(type=0, mi=MOUSEINPUT(round(args['x']*65535), round(args['y']*65535), data, flags, 0, 0))])
        if event == 'down': self.buttons.add(args['button'])
        if event == 'up': self.buttons.discard(args['button'])

    def text(self, value):
        encoded = value.encode('utf-16-le')
        entries = []
        for n in range(0, len(encoded), 2):
            unit = int.from_bytes(encoded[n:n+2], 'little')
            entries.extend([INPUT(type=1, ki=KEYBDINPUT(0, unit, 4, 0, 0)), INPUT(type=1, ki=KEYBDINPUT(0, unit, 6, 0, 0))])
        self.send(entries)

    def release(self):
        for code in list(self.keys):
            try: self.key(code, True)
            except Exception: pass
        for button in list(self.buttons):
            try: self.send([INPUT(type=0, mi=MOUSEINPUT(0, 0, 0, {0:4, 1:64, 2:16}[button], 0, 0))])
            except Exception: pass
        self.keys.clear(); self.buttons.clear()


class Companion:
    def __init__(self):
        self.config = json.loads((BASE / 'desktop.json').read_text(encoding='utf-8-sig'))
        self.inputs = InputController()
        self.root = tk.Tk(); self.root.title('ManagerPC — maktab nazorati')
        self.root.geometry(f'340x95+{self.root.winfo_screenwidth()-355}+{self.root.winfo_screenheight()-155}')
        self.root.resizable(False, False); self.root.attributes('-topmost', True)
        self.root.configure(bg='#153f35')
        self.label = tk.Label(self.root, text='ManagerPC: ulanish kutilmoqda', bg='#153f35', fg='white', font=('Segoe UI', 10, 'bold'))
        self.label.pack(pady=(10, 5))
        self.pause_button = tk.Button(self.root, text='Kuzatuvni 5 daqiqaga to‘xtatish', command=self.pause)
        self.pause_button.pack()
        self.root.protocol('WM_DELETE_WINDOW', self.pause)
        self.paused_until, self.last_connection, self.mode, self.ui_mode = 0, 0, 'idle', 'idle'
        self.quality, self.error = 'grid', ''
        self.commands, self.results = queue.Queue(), queue.Queue()
        self.completed = collections.OrderedDict()
        self.inflight = set()
        self.overlay, self.overlay_until = None, 0
        self.root.after(100, self.tick)
        threading.Thread(target=self.network, daemon=True).start()

    def paused(self): return time.monotonic() < self.paused_until

    def pause(self):
        self.paused_until = 0 if self.paused() else time.monotonic() + 300
        self.inputs.release(); self.unfocus()

    def unfocus(self):
        if self.overlay:
            self.overlay.destroy(); self.overlay = None

    def message(self, text):
        dialog = tk.Toplevel(self.root); dialog.title('ManagerPC — o‘qituvchidan xabar')
        dialog.attributes('-topmost', True)
        tk.Label(dialog, text=text, wraplength=500, justify='left', font=('Segoe UI', 14), padx=25, pady=25).pack()
        tk.Button(dialog, text='Tushunarli', command=dialog.destroy, padx=20, pady=6).pack(pady=15)

    def execute(self, command):
        identifier = command['id']
        if identifier in self.completed: return self.completed[identifier]
        result = {'id': identifier, 'ok': True}
        try:
            if self.paused() or not available_desktop(): raise ValueError('Sessiya pauzada yoki Windows ekrani qulflangan')
            kind, args = command['kind'], validate_action(command['kind'], command['args'])
            if kind in ('input', 'text'):
                if self.mode != 'control' or time.monotonic() - self.last_connection > 5:
                    raise ValueError('Boshqaruv sessiyasi tugagan')
                if kind == 'input': self.inputs.event(args)
                else: self.inputs.text(args['text'])
            elif kind == 'message': self.message(args['text'])
            elif kind == 'open_url':
                if not webbrowser.open(args['url']): raise ValueError('Brauzer ishga tushmadi')
            elif kind == 'lock':
                self.inputs.release()
                if not ctypes.windll.user32.LockWorkStation(): raise ValueError('Windows qulflanmadi')
            elif kind == 'focus':
                self.unfocus(); self.overlay = tk.Toplevel(self.root)
                self.overlay.title('ManagerPC — darsga e’tibor'); self.overlay.attributes('-fullscreen', True)
                self.overlay.attributes('-topmost', True); self.overlay.configure(bg='#123e34')
                tk.Label(self.overlay, text='Darsga e’tibor bering', bg='#123e34', fg='white', font=('Segoe UI', 36)).pack(expand=True)
                tk.Button(self.overlay, text='Yopish (Esc)', command=self.unfocus, padx=20, pady=10).pack(pady=40)
                self.overlay.bind('<Escape>', lambda _: self.unfocus())
                self.overlay.protocol('WM_DELETE_WINDOW', self.unfocus)
                self.overlay_until = time.monotonic() + args['seconds']
            elif kind == 'unfocus': self.unfocus()
            else: raise ValueError('Qo‘llab-quvvatlanmaydigan amal')
        except Exception as exc: result.update(ok=False, error=str(exc)[:300])
        self.completed[identifier] = result
        if len(self.completed) > 600: self.completed.popitem(last=False)
        return result

    def tick(self):
        connected = time.monotonic() - self.last_connection < 5
        if not connected or self.paused() or self.mode != 'control': self.inputs.release()
        if self.overlay and (time.monotonic() > self.overlay_until or not connected or self.paused()): self.unfocus()
        text = 'Mahalliy pauza yoqilgan' if self.paused() else ('Aloqa yo‘q' if not connected else {'idle':'Ulangan · kuzatuv yo‘q', 'view':'O‘qituvchi ekranni ko‘rmoqda', 'control':'O‘qituvchi kompyuterni boshqarmoqda'}[self.mode])
        self.label.configure(text='ManagerPC: ' + text)
        self.ui_mode = self.mode if connected else 'idle'
        self.pause_button.configure(text='Kuzatuvga ruxsat berish' if self.paused() else 'Kuzatuvni 5 daqiqaga to‘xtatish')
        for _ in range(40):
            try: command = self.commands.get_nowait()
            except queue.Empty: break
            self.results.put(self.execute(command)); self.inflight.discard(command['id'])
        self.root.after(100, self.tick)

    def network(self):
        results, windows, last_windows = [], [], 0
        while True:
            try:
                while True:
                    try: results.append(self.results.get_nowait())
                    except queue.Empty: break
                accessible = available_desktop()
                paused = self.paused() or not accessible
                frame = None
                if not paused and self.ui_mode in ('view', 'control') and time.monotonic()-self.last_connection < 5:
                    shot = ImageGrab.grab(all_screens=False)
                    shot.thumbnail((1280, 800) if self.quality == 'detail' else (480, 300), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO(); shot.convert('RGB').save(buffer, 'JPEG', quality=60)
                    frame = base64.b64encode(buffer.getvalue()).decode()
                if time.monotonic() - last_windows > 5:
                    windows = open_windows() if accessible else []; last_windows = time.monotonic()
                response = request(self.config, '/desktop/poll', {'id': self.config['id'], 'token': self.config['token'],
                    'paused': paused, 'user': getpass.getuser(), 'windows': windows, 'error': self.error,
                    'results': results, 'frame': frame}, timeout=4)
                results = []; self.error = ''
                self.mode = response['session']['mode']; self.quality = response['session']['quality']
                self.last_connection = time.monotonic()
                for command in response['commands']:
                    if command['expires'] <= response['server_time']: continue
                    if command['id'] not in self.inflight:
                        self.inflight.add(command['id']); self.commands.put(command)
            except Exception as exc:
                self.error = str(exc)[:300]; self.mode = 'idle'
            time.sleep(.65 if self.mode != 'idle' else 2)

    def run(self): self.root.mainloop()


def main():
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass
    # A companion is allowed once per interactive session.
    ctypes.windll.kernel32.CreateMutexW.restype = wintypes.HANDLE
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'Local\\ManagerPCDesktop')
    if ctypes.windll.kernel32.GetLastError() == 183: return
    try: Companion().run()
    except Exception as exc:
        error_dir = Path(os.environ.get('LOCALAPPDATA', '.')) / 'ManagerPC-Desktop'
        error_dir.mkdir(parents=True, exist_ok=True)
        (error_dir / 'error.txt').write_text(str(exc), encoding='utf-8')
    finally:
        ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        import win32gui, win32process
        assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        root = tk.Tk(); root.withdraw(); root.update_idletasks(); root.destroy()
    else: main()
