"""Isolated UI fixture. No desktop capture and no machine actions are executed."""
import io
import os
from pathlib import Path
import threading
import time
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
os.environ['LOCALAPPDATA'] = str(ROOT / 'build' / 'ui-fixture')
import server_v4 as server

server.state.update({'global': {'domains':['youtube.com'], 'apps':[]}, 'pcs':{}, 'devices':{}, 'packages':{}})
server.CERT = server.make_certificate(server.DATA)
for n in range(1, 7): server.state['pcs'][f'SINOV-PC-{n:02d}'] = {'domains':[], 'apps':[]}


def fixtures():
    while True:
        with server.lock:
            for n, host in enumerate(server.state['pcs'], 1):
                if n > 4: continue
                server.seen[host] = {'time':time.time(),'ip':f'192.168.1.{n+20}','version':'4.0','error':'',
                    'system':{'os':'Windows 11 — sinov ma’lumoti','cpu':'4 yadro','ram':'8 GB','disk_free':'128 GB'},
                    'inventory':{'running':['notepad.exe','chrome.exe'], 'installed':[f'sample-{i:02d}.exe' for i in range(45)]}}
                server.hub.desktops[host] = {'time':time.time(),'paused':False,'user':'Sinov foydalanuvchi',
                    'windows':[{'name':'notepad.exe','title':'SINOV — dars topshirigi'}], 'error':''}
                if server.hub.active(host)['mode'] != 'idle':
                    image = Image.new('RGB',(960,540),'#e2eee5'); draw = ImageDraw.Draw(image)
                    draw.rectangle((0,0,960,44), fill='#1e5040'); draw.text((24,17), 'ManagerPC — TEST SCREEN', fill='white')
                    draw.rectangle((40,85,920,475), fill='white'); draw.text((70,120),host+' — SYNTHETIC TEST IMAGE',fill='#19392a')
                    draw.text((70,160),'No real student screen is captured.',fill='#54725b')
                    output=io.BytesIO();image.save(output,'JPEG')
                    server.hub.frames[host]={'time':time.time(),'data':output.getvalue()}
        time.sleep(.5)


if __name__ == '__main__':
    threading.Thread(target=fixtures,daemon=True).start()
    print('Fixture only: http://127.0.0.1:8785',flush=True)
    server.ThreadingHTTPServer(('127.0.0.1',8785),server.Handler).serve_forever()
