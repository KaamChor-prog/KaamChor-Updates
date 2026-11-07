import hashlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app_updates as u

class Response(io.BytesIO):
    def geturl(self):return 'https://example.com/app.exe'

class Updates(unittest.TestCase):
    def test_versions(self):
        self.assertGreater(u.version('3.10.0'),u.version('3.9.9'))
        for bad in ('3.1','latest',None,'3.1.0-beta'):
            with self.assertRaises(ValueError):u.version(bad)
    def test_feed(self):
        release=dict(version='3.5.0',url='https://example.com/app.exe',sha256='a'*64,size=10)
        with patch.object(u,'UPDATE_FEED_URL','https://example.com/latest.json'),patch.object(u,'fetch_json',return_value=release):
            self.assertEqual(u.check_update(),release)
            release['url']='http://example.com/app.exe'
            with self.assertRaises(ValueError):u.check_update()
    def test_download_verification(self):
        data=b'MZexample executable'
        release=dict(url='https://example.com/app.exe',size=len(data),sha256=hashlib.sha256(data).hexdigest())
        with patch.object(u,'urlopen',return_value=Response(data)):
            path=u.download_update(release)
            self.assertEqual(path.read_bytes(),data)
            path.unlink();path.parent.rmdir()
        release['sha256']='0'*64
        with patch.object(u,'urlopen',return_value=Response(data)):
            with self.assertRaises(ValueError):u.download_update(release)
    def test_no_downgrade(self):
        with patch.object(u,'UPDATE_FEED_URL','https://example.com/latest.json'),patch.object(u,'fetch_json',return_value={'version':'3.0.0'}):
            self.assertIsNone(u.check_update())

if __name__=='__main__':unittest.main()
