import asyncio
import csv
import importlib.util
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch
import types

spec = importlib.util.spec_from_file_location('app', Path(__file__).parents[1] / 'Aryan_Remix.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class Tests(unittest.TestCase):
    def fixture(self, folder):
        p = Path(folder) / 'students.csv'
        p.write_text('Adobe Email,Password,Template Link,Notes\na@school.test, secret ,https://new.express.adobe.com/template/one,keep me\n,,,\nb@school.test,p2,https://new.express.adobe.com/template/two,second\n', encoding='utf-8')
        return p

    def test_input_row_mapping_and_password(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.fixture(d)
            _, _, rows = app.read_rows(p)
            self.assertEqual([r['row'] for r in rows], [2, 4])
            self.assertEqual(rows[0]['password'], ' secret ')

    def test_output_resume_and_original(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.fixture(d)
            before = p.read_bytes()
            headers, values, rows = app.read_rows(p)
            r = app.Results(p, headers, values)
            r.save(rows[1], 'Done', 'Complete', 'https://new.express.adobe.com/webpage/newlink')
            self.assertEqual(p.read_bytes(), before)
            with r.target.open(encoding='utf-8-sig') as f:
                output = list(csv.reader(f))
            self.assertEqual(output[3][3], 'second')
            self.assertEqual(output[3][4], 'https://new.express.adobe.com/webpage/newlink')
            self.assertEqual(output[1][4], '')
            self.assertEqual(app.Results(p, headers, values).previous(rows[1])['status'], 'Done')
            changed = dict(rows[1], email='different@school.test')
            self.assertEqual(r.previous(changed), {})
            self.assertNotIn('secret', r.journal.read_text())

    def test_domain_validation(self):
        for url in ['http://adobe.com/page/x', 'https://adobe.com.evil.test/page/x', 'https://user@adobe.com/page/x', 'javascript:alert(1)']:
            self.assertFalse(app.adobe_url(url))
        self.assertTrue(app.adobe_url('https://express.adobe.com/page/x'))

    def test_bad_headers(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.csv'
            p.write_text('Email,Adobe Email,Password,Link\na,b,p,https://adobe.com/page/x')
            with self.assertRaises(ValueError):
                app.read_rows(p)

    def test_stop_interrupts_wait(self):
        stop = threading.Event()
        engine = app.Engine(stop, queue.Queue(), 1, 60)
        stop.set()
        with self.assertRaises(app.Stopped):
            asyncio.run(engine.sleep())

class FlowTests(unittest.TestCase):
    def test_isolated_sessions_publish_once_and_resume(self):
        contexts = []
        actions = []
        class Keyboard:
            async def press(self, key):
                pass
        class Page:
            keyboard = Keyboard()
            async def goto(self, *args, **kwargs):
                pass
        class Context:
            def __init__(self):
                self.closed = False
                contexts.append(self)
            async def grant_permissions(self, *args, **kwargs):
                pass
            async def new_page(self):
                return Page()
            async def close(self):
                self.closed = True
        class Browser:
            async def new_context(self, **kwargs):
                return Context()
            async def close(self):
                pass
        class Chromium:
            async def launch(self, **kwargs):
                self.kwargs = kwargs
                return Browser()
        class Playwright:
            chromium = Chromium()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
        module = types.ModuleType('playwright.async_api')
        module.async_playwright = Playwright
        class Engine(app.Engine):
            async def open_remix(self, context, item):
                pass
            async def ready_login(self, context, item):
                return Page()
            async def click(self, context, label, timeout=45):
                actions.append((id(context), label))
            async def ensure_published(self, context, item, results):
                results.save(item, 'Running', 'Create link requested')
                await self.click(context, r'^Create link$')
            async def published_link(self, context, template):
                return 'https://new.express.adobe.com/webpage/' + str(id(context))
        with tempfile.TemporaryDirectory() as d:
            p = Tests().fixture(d)
            with patch.dict('sys.modules', {'playwright': types.ModuleType('playwright'), 'playwright.async_api': module}):
                engine = Engine(threading.Event(), queue.Queue(), 2, 60)
                asyncio.run(engine.run(p))
                self.assertEqual(len(contexts), 2)
                self.assertTrue(all(c.closed for c in contexts))
                self.assertEqual(sum(label == r'^Create link$' for _, label in actions), 2)
                asyncio.run(engine.run(p))
                self.assertEqual(len(contexts), 2)  # Done rows do not republish.
                headers, values, rows = app.read_rows(p)
                results = app.Results(p, headers, values)
                results.save(rows[0], 'Review', 'Capture link')
                asyncio.run(engine.run(p))
                self.assertEqual(len(contexts), 2)  # Ambiguous publish is held for review.

if __name__ == '__main__':
    unittest.main()
