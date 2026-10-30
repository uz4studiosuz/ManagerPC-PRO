import base64
import ctypes
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parent
TEMP = tempfile.TemporaryDirectory(dir=ROOT, prefix='test-v4-')
os.environ['LOCALAPPDATA'] = TEMP.name
import server_v4 as server
from remote_hub import Hub, validate_action
from secure_transport import request, make_certificate
from PIL import Image


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.hub = Hub()
        self.hub.desktops['PC-01'] = {'time': time.time(), 'paused': False}

    def test_lease_expiry_releases_input_and_frame(self):
        self.hub.lease('PC-01', 'control')
        self.hub.queue('PC-01', 'input', {'event': 'key_down', 'code': 'KeyA'})
        self.hub.frames['PC-01'] = {'time': time.time(), 'data': b'frame'}
        self.hub.leases['PC-01']['until'] = time.time()-1
        self.assertEqual(self.hub.active('PC-01')['mode'], 'idle')
        self.assertNotIn('PC-01', self.hub.frames)
        with self.assertRaises(ValueError): self.hub.queue('PC-01', 'input', {'event': 'key_up', 'code': 'KeyA'})

    def test_pause_and_missing_desktop_refuse_commands(self):
        self.hub.desktops['PC-01']['paused'] = True
        with self.assertRaises(ValueError): self.hub.queue('PC-01', 'message', {'text': 'test'})
        with self.assertRaises(ValueError): self.hub.queue('PC-02', 'open_url', {'url': 'https://example.com'})

    def test_commands_expire_and_ack_is_role_scoped(self):
        identifier = self.hub.queue('PC-01', 'restart', {})
        self.assertEqual(self.hub.commands('PC-01', 'desktop', [{'id': identifier, 'ok': True}]), [])
        self.assertIn(identifier, self.hub.pending['PC-01'])
        self.hub.commands('PC-01', 'agent', [{'id': identifier, 'ok': True}])
        self.assertNotIn(identifier, self.hub.pending['PC-01'])
        identifier = self.hub.queue('PC-01', 'message', {'text': 'test'})
        self.hub.pending['PC-01'][identifier]['expires'] = 0
        self.assertEqual(self.hub.commands('PC-01', 'desktop', []), [])

    def test_command_validation(self):
        for kind, args in [('shell', {}), ('open_url', {'url':'file:///C:/Windows/notepad.exe'}),
                           ('open_url', {'url':'javascript:alert(1)'}), ('input', {'event':'move','x':float('nan'),'y':0}),
                           ('input', {'event':'key_down','code':'UNKNOWN'}), ('focus', {'seconds':9999})]:
            with self.assertRaises(ValueError): validate_action(kind, args)

    def test_move_events_coalesce(self):
        self.hub.lease('PC-01', 'control')
        for n in range(10): self.hub.queue('PC-01', 'input', {'event':'move','x':n/10,'y':0})
        self.assertEqual(len(self.hub.pending['PC-01']), 1)


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.CERT = make_certificate(server.DATA)
        cls.admin = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.agent = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.agent.agent_listener = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(server.CERT[0]), str(server.CERT[1]))
        cls.agent.socket = context.wrap_socket(cls.agent.socket, server_side=True)
        cls.threads = []
        for http in (cls.admin, cls.agent):
            thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start(); cls.threads.append(thread)
        cls.config = {'server':f'https://127.0.0.1:{cls.agent.server_port}', 'certificate':str(server.CERT[0]), 'fingerprint':server.CERT[2]}

    @classmethod
    def tearDownClass(cls):
        for http in (cls.admin, cls.agent): http.shutdown(); http.server_close()
        for thread in cls.threads: thread.join()

    def setUp(self):
        server.state.update(global_={})
        server.state['global'] = {'domains': [], 'apps': []}
        server.state['pcs'] = {}; server.state['devices'] = {}; server.seen.clear(); server.hub = Hub()
        self.package = secrets.token_urlsafe(24)
        server.state['packages'] = {server.digest(self.package): {'expires':time.time()+60}}
        self.keys = request(self.config, '/agent/enroll', {'package':self.package,'hostname':'PC-01'})

    def admin_request(self, path, body=None, valid=True, host=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.admin.server_port, timeout=5)
        headers = {'Origin':f'http://127.0.0.1:{self.admin.server_port}', 'Content-Type':'application/json'}
        if valid: headers['X-ManagerPC'] = server.CSRF
        if host: headers['Host'] = host
        connection.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), headers)
        response = connection.getresponse(); status = response.status; raw = response.read(); connection.close()
        return status, raw

    def test_roles_certificate_and_csrf(self):
        with self.assertRaises(ValueError):
            request(dict(self.config, fingerprint='0'*64), '/agent/heartbeat', {})
        with self.assertRaises(ValueError):
            request(self.config, '/agent/heartbeat', {'id':self.keys['id'],'token':self.keys['desktop_token']})
        self.assertEqual(self.admin_request('/api/policy', {'host':'*','policy':{'domains':[],'apps':[]}}, valid=False)[0], 403)
        self.assertEqual(self.admin_request('/api/state', host='attacker.example')[0], 403)
        self.assertEqual(self.admin_request('/api/state')[0], 200)

    def test_duplicate_hostname_cannot_replace_existing_identity(self):
        with self.assertRaises(ValueError): request(self.config, '/agent/enroll', {'package':self.package,'hostname':'PC-01'})
        result = request(self.config, '/agent/enroll', {'package':self.package,'hostname':'PC-01','id':self.keys['id'],'token':self.keys['token']})
        self.assertEqual(result['id'], self.keys['id'])
        self.assertNotEqual(result['desktop_token'], self.keys['desktop_token'])

    def test_complete_desktop_flow_and_revocation(self):
        credentials = {'id':self.keys['id'],'token':self.keys['desktop_token']}
        reply = request(self.config, '/desktop/poll', dict(credentials, paused=False, user='Student', windows=[]))
        self.assertEqual(reply['session']['mode'], 'idle')
        status, _ = self.admin_request('/api/session', {'host':'PC-01','mode':'control'})
        self.assertEqual(status, 200)
        status, raw = self.admin_request('/api/action', {'host':'PC-01','kind':'message','args':{'text':'test'}})
        identifier = json.loads(raw)['id']; self.assertEqual(status, 200)
        image = io.BytesIO(); Image.new('RGB',(32,20)).save(image,'JPEG')
        reply = request(self.config, '/desktop/poll', dict(credentials, paused=False, frame=base64.b64encode(image.getvalue()).decode()))
        self.assertEqual(reply['commands'][0]['id'], identifier)
        self.assertEqual(self.admin_request('/api/frame?host=PC-01')[0], 200)
        request(self.config, '/desktop/poll', dict(credentials, paused=True, results=[{'id':identifier,'ok':True}]))
        self.assertEqual(self.admin_request('/api/frame?host=PC-01')[0], 404)
        self.assertEqual(self.admin_request('/api/revoke', {'host':'PC-01'})[0], 200)
        with self.assertRaises(ValueError): request(self.config, '/desktop/poll', credentials)

    def test_backup_contains_no_pairing_or_device_secrets(self):
        status, raw = self.admin_request('/api/backup')
        self.assertEqual(status, 200)
        for token in self.keys.values(): self.assertNotIn(str(token).encode(), raw)
        self.assertEqual(set(json.loads(raw)), {'format','global','pcs'})

    def test_tls_listener_never_exposes_admin_routes(self):
        with self.assertRaises(ValueError): request(self.config, '/api/action', {'host':'PC-01','kind':'restart'})


class WindowsHelpersTests(unittest.TestCase):
    def test_input_struct_layout_and_execution_is_idempotent(self):
        import desktop_agent
        if ctypes.sizeof(ctypes.c_void_p) == 8: self.assertEqual(ctypes.sizeof(desktop_agent.INPUT), 40)
        client = desktop_agent.Companion.__new__(desktop_agent.Companion)
        client.completed = __import__('collections').OrderedDict()
        client.paused_until = 0; client.message = Mock()
        command = {'id':'once','kind':'message','args':{'text':'lesson'}}
        with patch.object(desktop_agent, 'available_desktop', return_value=True):
            self.assertTrue(client.execute(command)['ok'])
            self.assertTrue(client.execute(command)['ok'])
        client.message.assert_called_once_with('lesson')

    def test_browser_policy_preserves_other_admin_entries(self):
        import browser_rules
        registry = {p:{'1':'school.example'} for p in browser_rules.PATHS}
        class Key:
            def __init__(self, path): self.path = path
            def __enter__(self): return self
            def __exit__(self, *args): pass
        fake = Mock()
        fake.HKEY_LOCAL_MACHINE=0; fake.KEY_ALL_ACCESS=1; fake.KEY_WOW64_64KEY=2; fake.REG_SZ=1
        fake.CreateKeyEx.side_effect=lambda root,path,*args:Key(path)
        fake.QueryInfoKey.side_effect=lambda key:(0,len(registry[key.path]),0)
        fake.EnumValue.side_effect=lambda key,n:(*list(registry[key.path].items())[n],1)
        fake.SetValueEx.side_effect=lambda key,name,res,kind,value:registry[key.path].__setitem__(name,value)
        fake.DeleteValue.side_effect=lambda key,name:registry[key.path].pop(name)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, patch.dict(sys.modules, {'winreg':fake}):
            browser_rules.apply(['youtube.com'], directory)
            self.assertIn('youtube.com', registry[browser_rules.PATHS[0]].values())
            browser_rules.remove(directory)
            self.assertEqual(registry, {p:{'1':'school.example'} for p in browser_rules.PATHS})


if __name__ == '__main__': unittest.main()
