import json, os, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch

temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
os.environ['LOCALAPPDATA'] = temp.name
import agent, server

class ManagerTest(unittest.TestCase):
    def test_hosts_preserve_and_remove(self):
        path = Path(temp.name) / 'hosts'
        path.write_text('127.0.0.1 localhost\n', encoding='utf-8')
        with patch.object(agent, 'HOSTS', path), patch.object(agent.subprocess, 'run'):
            agent.update_hosts(['youtube.com'])
            self.assertIn('0.0.0.0 www.youtube.com', path.read_text())
            self.assertIn('0.0.0.0 m.youtube.com', path.read_text())
            self.assertIn('0.0.0.0 youtu.be', path.read_text())
            agent.update_hosts([])
            self.assertIn('127.0.0.1 localhost', path.read_text())
            self.assertNotIn('youtube.com', path.read_text())

    def test_policy_validation(self):
        p = server.clean_policy({'domains':['https://youtube.com/a'], 'apps':['Game.exe']})
        self.assertEqual(p['domains'], ['youtube.com']); self.assertEqual(p['apps'], ['game.exe'])
        with self.assertRaises(ValueError): server.clean_policy({'domains':['bad domain'], 'apps':[]})
        with self.assertRaises(ValueError): server.clean_policy({'domains':[], 'apps':['../game.exe']})
        with self.assertRaises(ValueError): server.clean_policy({'domains':[], 'apps':['svchost.exe']})

    def test_veyon_launch_is_limited_to_known_hosts(self):
        server.state['pcs']['PC-01'] = {'domains': [], 'apps': []}
        with patch.object(server, 'veyon_program', return_value=r'C:\Veyon\veyon-wcli.exe'), patch.object(server.subprocess, 'Popen') as run:
            server.launch_veyon('control', 'PC-01')
            self.assertEqual(run.call_args.args[0][1:], ['remoteaccess', 'control', 'PC-01'])
            with self.assertRaises(ValueError): server.launch_veyon('control', 'UNKNOWN')
            with self.assertRaises(ValueError): server.launch_veyon('control', 'PC-01 & calc')
            with self.assertRaises(ValueError): server.launch_veyon('shell', 'PC-01')

if __name__ == '__main__': unittest.main()
