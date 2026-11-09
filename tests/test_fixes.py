import asyncio
import queue
import threading
import unittest
import types
from unittest.mock import AsyncMock, MagicMock, patch
from test_app import app


class FixTests(unittest.TestCase):
    def engine(self):
        return app.Engine(threading.Event(), queue.Queue(), 1, 60)

    def test_share_preparation_is_bounded_and_closes_panel(self):
        engine = self.engine()
        marker, share, page = MagicMock(), MagicMock(), MagicMock()
        page.url = 'https://new.express.adobe.com/editor'
        page.keyboard.press = AsyncMock()
        marker.is_enabled = AsyncMock(return_value=False)
        share.is_enabled = AsyncMock(return_value=True)
        share.click = AsyncMock()
        engine.button = AsyncMock(side_effect=lambda p, label: share if label == r'^Share$' else marker if label == r'^Assign$' else None)
        engine.sleep = AsyncMock()
        async def run():
            state = {'count':0}
            for _ in range(5):
                await engine.warmup_share(page, {'row':2}, state)
            self.assertEqual(state['count'], 2)
        asyncio.run(run())
        self.assertEqual(share.click.await_count, 2)
        self.assertEqual(page.keyboard.press.await_count, 2)
        page.keyboard.press.assert_awaited_with('Escape')

    def test_share_preparation_does_not_click_public_viewer(self):
        engine = self.engine()
        share = MagicMock()
        share.click = AsyncMock()
        engine.button = AsyncMock(side_effect=lambda p, label: share if label == r'^Share$' else None)
        asyncio.run(engine.warmup_share(MagicMock(url='https://express.adobe.com/publishedV2/test'), {'row':2}, {'count':0}))
        share.click.assert_not_awaited()

    def test_share_preparation_stops_when_marker_ready(self):
        engine = self.engine()
        marker = MagicMock()
        marker.is_enabled = AsyncMock(return_value=True)
        engine.button = AsyncMock(return_value=marker)
        asyncio.run(engine.warmup_share(MagicMock(url='https://new.express.adobe.com/editor'), {'row':2}, {'count':0}))
        marker.click.assert_not_called()

    def test_assign_and_turn_in_readiness(self):
        async def run():
            for enabled_label in (r'^Assign$', r'^Turn in$', None):
                engine = self.engine()
                button = MagicMock()
                button.is_enabled = AsyncMock(return_value=True)
                engine.button = AsyncMock(side_effect=lambda page, label: button if label == enabled_label else None)
                page = MagicMock(url='https://new.express.adobe.com/editor')
                self.assertEqual(await engine.editor_ready(page), enabled_label is not None)
                button.click.assert_not_called()
        asyncio.run(run())

    def test_login_before_remix_is_handed_to_login_loop(self):
        async def run():
            for url in ('https://accounts.google.com/v3/signin/identifier',
                        'https://login.microsoftonline.com/tenant/oauth2/authorize',
                        'https://auth.services.adobe.com/en_US/index.html'):
                engine = self.engine()
                root = MagicMock(url=url)
                root.locator.return_value = object()
                page = MagicMock(url=url, frames=[root])
                page.is_closed.return_value = False
                engine.visible = AsyncMock(side_effect=lambda value: value)
                engine.editor_ready = AsyncMock(return_value=False)
                engine.button = AsyncMock(return_value=None)
                await engine.open_remix(MagicMock(pages=[page]), {'row': 2})
                engine.editor_ready.assert_not_awaited()
        asyncio.run(run())

    def test_missing_remix_skips_loaded_viewer(self):
        engine = self.engine()
        page = MagicMock(url='https://express.adobe.com/publishedV2/template')
        page.is_closed.return_value = False
        context = MagicMock(pages=[page])
        engine.editor_ready = AsyncMock(return_value=False)
        engine.button = AsyncMock(side_effect=lambda page, label: object() if label == r'^Share$' else None)
        engine.sleep = AsyncMock()
        clock = MagicMock(side_effect=[0, 1, 46])
        with patch.object(app, 'time', types.SimpleNamespace(monotonic=clock)):
            with self.assertRaises(app.NoRemix):
                asyncio.run(engine.open_remix(context, {'row':2}))

    def test_unloaded_viewer_is_not_classified_missing_remix(self):
        engine = self.engine()
        page = MagicMock(url='https://express.adobe.com/publishedV2/template')
        page.is_closed.return_value = False
        engine.editor_ready = AsyncMock(return_value=False)
        engine.button = AsyncMock(return_value=None)
        engine.sleep = AsyncMock()
        clock = MagicMock(side_effect=[0, 1, 46])
        with patch.object(app, 'time', types.SimpleNamespace(monotonic=clock)):
            with self.assertRaises(TimeoutError):
                asyncio.run(engine.open_remix(MagicMock(pages=[page]), {'row':2}))

    def test_microsoft_school_host_is_allowed_exactly(self):
        self.assertTrue(app.trusted_login_url('https://login.microsoftonline.com/tenant/oauth2/authorize'))
        self.assertFalse(app.trusted_login_url('https://login.microsoftonline.com.evil.test/password'))
        self.assertFalse(app.trusted_login_url('http://login.microsoftonline.com/password'))
        self.assertFalse(app.trusted_login_url('https://user@login.microsoftonline.com/password'))

    def test_google_login_host_is_exact(self):
        self.assertTrue(app.trusted_login_url('https://accounts.google.com/v3/signin/identifier'))
        for url in ('https://accounts.google.com.evil.test', 'http://accounts.google.com', 'https://user@accounts.google.com'):
            self.assertFalse(app.trusted_login_url(url))

    def test_google_email_then_password_are_submitted_once(self):
        engine = self.engine()
        root = MagicMock(url='https://auth.services.adobe.com/en_US/index.html')
        field, submit = MagicMock(), MagicMock()
        field.fill = AsyncMock()
        field.input_value = AsyncMock(return_value='student@example.com')
        submit.is_enabled = AsyncMock(return_value=True)
        submit.click = AsyncMock()
        state = {'password': False}
        def locate(selector):
            if 'Next' in selector:
                return submit
            if 'password' in selector:
                return field if state['password'] else None
            return field
        root.locator.side_effect = locate
        root.get_by_text.return_value = None
        root.get_by_role.return_value = submit
        engine.visible = AsyncMock(side_effect=lambda value: value)
        async def run():
            seen = set()
            item = {'row': 2, 'email': 'student@example.com', 'password': ' test pass '}
            page = MagicMock(frames=[root])
            await engine.handle_login_fields(page, item, seen)
            await engine.handle_login_fields(page, item, seen)
            root.url = 'https://accounts.google.com/v3/signin/identifier'
            await engine.handle_login_fields(page, item, seen)
            await engine.handle_login_fields(page, item, seen)
            state['password'] = True
            root.url = 'https://accounts.google.com/v3/signin/challenge/pwd'
            field.input_value.return_value = item['password']
            await engine.handle_login_fields(page, item, seen)
            await engine.handle_login_fields(page, item, seen)
        asyncio.run(run())
        self.assertEqual(field.fill.await_count, 3)
        self.assertEqual(submit.click.await_count, 3)
        field.fill.assert_any_await('student@example.com', timeout=3000)
        field.fill.assert_any_await(' test pass ', timeout=3000)

    def test_google_identifier_text_input_and_empty_rerender(self):
        engine = self.engine()
        root = MagicMock(url='https://accounts.google.com/v3/signin/identifier')
        field, submit = MagicMock(), MagicMock()
        field.fill = AsyncMock()
        field.input_value = AsyncMock(return_value='student@example.com')
        submit.is_enabled = AsyncMock(return_value=True)
        submit.click = AsyncMock()
        root.get_by_text.return_value = None
        def locate(selector):
            if '#identifierId' in selector:
                return field
            if 'identifierNext' in selector:
                return submit
            return None
        root.locator.side_effect = locate
        engine.visible = AsyncMock(side_effect=lambda value: value)
        async def run():
            seen = {(root, root.url, 'email')}
            field.input_value.side_effect = ['', 'student@example.com']
            await engine.handle_login_fields(MagicMock(frames=[root]),
                {'row': 2, 'email': 'student@example.com'}, seen)
        asyncio.run(run())
        field.fill.assert_awaited_once_with('student@example.com', timeout=3000)
        submit.click.assert_awaited_once()

    def test_provider_repeated_email_is_bounded(self):
        async def run(host):
            engine = self.engine()
            root = MagicMock(url='https://' + host + '/signin')
            email, submit = MagicMock(), MagicMock()
            value = {'text': ''}
            async def fill(text, **kwargs):
                value['text'] = text
            email.fill = AsyncMock(side_effect=fill)
            email.input_value = AsyncMock(side_effect=lambda **kwargs: value['text'])
            submit.is_enabled = AsyncMock(return_value=True)
            submit.click = AsyncMock()
            root.get_by_text.return_value = None
            root.get_by_role.return_value = submit
            def locate(selector):
                if '#identifierId' in selector:
                    return email
                if 'identifierNext' in selector:
                    return submit
                return None
            root.locator.side_effect = locate
            engine.visible = AsyncMock(side_effect=lambda x: x)
            page, seen = MagicMock(frames=[root]), set()
            item = {'row': 2, 'email': 'student@example.com'}
            await engine.handle_login_fields(page, item, seen)
            await engine.handle_login_fields(page, item, seen)
            self.assertEqual(submit.click.await_count, 1)
            value['text'] = ''  # A second identifier page at the same URL.
            await engine.handle_login_fields(page, item, seen)
            self.assertEqual(submit.click.await_count, 2)
            value['text'] = ''  # A persistent error must not loop forever.
            await engine.handle_login_fields(page, item, seen)
            self.assertEqual(submit.click.await_count, 2)
        for host in ('login.microsoftonline.com', 'accounts.google.com'):
            with self.subTest(host=host):
                asyncio.run(run(host))

    def test_password_inside_frame_is_filled_once(self):
        engine = self.engine()
        root = MagicMock()
        root.url = 'https://login.microsoftonline.com/tenant/oauth2/authorize'
        password, submit = MagicMock(), MagicMock()
        password.fill = AsyncMock()
        password.input_value = AsyncMock(return_value=' test pass ')
        submit.is_enabled = AsyncMock(return_value=True)
        submit.click = AsyncMock()
        root.locator.side_effect = lambda s: password if 'password' in s else None
        root.get_by_text.return_value = None
        root.get_by_role.return_value = submit
        engine.visible = AsyncMock(side_effect=lambda x: x)
        page = MagicMock(frames=[root])
        async def run():
            seen = set()
            item = {'row':2, 'email':'student@example.com', 'password':' test pass '}
            await engine.handle_login_fields(page, item, seen)
            await engine.handle_login_fields(page, item, seen)
        asyncio.run(run())
        password.fill.assert_awaited_once_with(' test pass ', timeout=3000)
        submit.click.assert_awaited_once()

    def test_stay_signed_in_selects_yes_once(self):
        engine = self.engine()
        root = MagicMock()
        root.url = 'https://login.microsoftonline.com/kmsi'
        yes = MagicMock()
        yes.is_enabled = AsyncMock(return_value=True)
        yes.click = AsyncMock()
        root.get_by_text.return_value = object()
        root.get_by_role.return_value = yes
        engine.visible = AsyncMock(side_effect=lambda x: x)
        async def run():
            seen = set()
            for _ in range(2):
                await engine.handle_login_fields(MagicMock(frames=[root]), {'row':2}, seen)
        asyncio.run(run())
        yes.click.assert_awaited_once()
        self.assertIn('Yes', root.get_by_role.call_args.kwargs['name'].pattern)

    def test_existing_published_link_skips_create(self):
        engine = self.engine()
        page, copy, results = MagicMock(), MagicMock(), MagicMock()
        page.url = 'https://express.adobe.com/id/project'
        page.is_closed.return_value = False
        copy.is_enabled = AsyncMock(return_value=True)
        engine.button = AsyncMock(side_effect=lambda p, label: copy if label == r'^Copy link$' else None)
        asyncio.run(engine.ensure_published(MagicMock(pages=[page]), {'row': 2}, results))
        results.save.assert_not_called()
        self.assertEqual(engine.button.await_count, 1)

    def test_new_publication_is_requested_once(self):
        engine = self.engine()
        page, create, results = MagicMock(), MagicMock(), MagicMock()
        page.url = 'https://express.adobe.com/id/project'
        page.is_closed.return_value = False
        create.is_enabled = AsyncMock(return_value=True)
        create.click = AsyncMock()
        engine.button = AsyncMock(side_effect=lambda p, label: create if label == r'^Create link$' else None)
        asyncio.run(engine.ensure_published(MagicMock(pages=[page]), {'row': 2}, results))
        create.click.assert_awaited_once()
        results.save.assert_called_once_with({'row': 2}, 'Running', 'Create link requested')

    def test_copy_waits_for_async_clipboard_without_reclick(self):
        engine = self.engine()
        context, page, copy = MagicMock(), MagicMock(), MagicMock()
        page.url = 'https://express.adobe.com/editor'
        context.grant_permissions = AsyncMock()
        page.bring_to_front = AsyncMock()
        # Clear, empty first read, then newly copied link.
        page.evaluate = AsyncMock(side_effect=[None, '', 'https://express.adobe.com/publishedV2/new'])
        copy.click = AsyncMock()
        engine.sleep = AsyncMock()
        result = asyncio.run(engine.copy_once(context, page, copy, 'https://express.adobe.com/publishedV2/original'))
        self.assertEqual(result, 'https://express.adobe.com/publishedV2/new')
        copy.click.assert_awaited_once()
        self.assertEqual(context.grant_permissions.call_args.kwargs['origin'], 'https://express.adobe.com')

    def test_failed_copy_is_not_retried(self):
        engine = self.engine()
        page, context, dialogs, copy = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        page.url = 'https://express.adobe.com/editor'
        page.is_closed.return_value = False
        page.get_by_role.return_value = dialogs
        dialogs.count = AsyncMock(return_value=0)
        page.locator.return_value.count = AsyncMock(return_value=0)
        context.pages = [page]
        copy.is_enabled = AsyncMock(return_value=True)
        engine.button = AsyncMock(return_value=copy)
        engine.copy_once = AsyncMock(side_effect=TimeoutError('No clipboard URL'))
        with self.assertRaises(TimeoutError):
            asyncio.run(engine.published_link(context, 'https://express.adobe.com/publishedV2/original'))
        engine.copy_once.assert_awaited_once()

    def test_original_link_with_tracking_changes_is_rejected(self):
        self.assertFalse(app.valid_published_link('https://express.adobe.com/publishedV2/original?x=2','https://express.adobe.com/publishedV2/original?x=1'))
        self.assertFalse(app.trusted_login_url('https://adobe.com.evil.test'))

if __name__ == '__main__':
    unittest.main()
