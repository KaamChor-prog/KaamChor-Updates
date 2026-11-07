import hashlib
import io
from pathlib import Path
import sys
import threading
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
        release=dict(version=f'{u.version(u.APP_VERSION)[0]+1}.0.0',url='https://example.com/app.exe',sha256='a'*64,size=10)
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
    def test_progress_and_retry_after_stall(self):
        data=b'MZ'+b'x'*100000
        release=dict(url='https://example.com/app.exe',size=len(data),sha256=hashlib.sha256(data).hexdigest())
        progress=[];messages=[]
        with patch.object(u,'urlopen',side_effect=[TimeoutError('stalled'),Response(data)]) as opened:
            path=u.download_update(release,lambda done,total:progress.append((done,total)),status=messages.append)
        self.assertEqual(opened.call_count,2)
        self.assertIn('Retrying',messages[1])
        self.assertEqual(progress[-1],(len(data),len(data)))
        self.assertTrue(any(0 < done < len(data) for done,total in progress))
        path.unlink();path.parent.rmdir()

    def test_stalls_have_bounded_retries(self):
        release=dict(url='https://example.com/app.exe',size=100,sha256='a'*64)
        with patch.object(u,'urlopen',side_effect=TimeoutError('stalled')) as opened:
            with self.assertRaisesRegex(TimeoutError,'3 attempts'):u.download_update(release)
        self.assertEqual(opened.call_count,3)

    def test_cancel_before_network(self):
        cancel=threading.Event();cancel.set()
        with patch.object(u,'urlopen') as opened:
            with self.assertRaises(u.DownloadCancelled):u.download_update({},cancel=cancel)
        opened.assert_not_called()

    def test_cancel_during_download(self):
        cancel=threading.Event();data=b'MZ'+b'x'*100000
        release=dict(url='https://example.com/app.exe',size=len(data),sha256=hashlib.sha256(data).hexdigest())
        def progress(done,total):
            if done:cancel.set()
        with patch.object(u,'urlopen',return_value=Response(data)):
            with self.assertRaises(u.DownloadCancelled):u.download_update(release,progress,cancel)

    def test_total_deadline_is_enforced(self):
        release=dict(url='https://example.com/app.exe',size=100,sha256='a'*64)
        with patch.object(u.time,'monotonic',side_effect=[0,181]),patch.object(u,'urlopen') as opened:
            with self.assertRaisesRegex(TimeoutError,'too long'):u.download_update(release)
        opened.assert_not_called()

    def test_no_downgrade(self):
        with patch.object(u,'UPDATE_FEED_URL','https://example.com/latest.json'),patch.object(u,'fetch_json',return_value={'version':'3.0.0'}):
            self.assertIsNone(u.check_update())

if __name__=='__main__':unittest.main()
