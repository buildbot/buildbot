# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import annotations

import json
import platform
import sys
from typing import TYPE_CHECKING
from typing import Any
from unittest.case import SkipTest

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.plugins.db import get_plugins
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import telegram
from buildbot.reporters import words
from buildbot.schedulers import forcesched
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.web import FakeRequest
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.unit.reporters.test_words import ContactMixin
from buildbot.util import httpclientservice
from buildbot.util import service
from buildbot.util import unicode2bytes

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class FakeChannel(service.AsyncService):
    pass


class FakeContact:
    def __init__(self, user: dict[str, Any] | None = None, channel: Any = None) -> None:
        super().__init__()
        self.user_id = user['id']  # type: ignore[index]
        self.user_info = user
        self.channel = FakeChannel
        self.channel.chat_info = channel.chat_info  # type: ignore[attr-defined]
        self.template = None
        self.messages = []  # type: ignore[var-annotated]

    def handleMessage(self, message: str, **kwargs: Any) -> defer.Deferred[str]:
        self.messages.append(message)
        return defer.succeed(message)


class TestTelegramContact(ContactMixin, unittest.TestCase):
    channelClass = telegram.TelegramChannel
    contactClass = telegram.TelegramContact

    class botClass(words.StatusBot):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.query_cache = {}  # type: ignore[var-annotated]

        def send_message(self, chat: Any, message: str, **kwargs: Any) -> dict[str, Any]:
            return {'message_id': 123}

        def edit_message(
            self, chat: Any, msgid: Any, message: str, **kwargs: Any
        ) -> dict[str, Any]:
            return {'message_id': 123}

        def delete_message(self, chat: Any, msgid: Any) -> None:
            pass

        def send_sticker(self, chat: Any, sticker: Any, **kwargs: Any) -> None:
            pass

        def edit_keyboard(self, chat: Any, msg: Any, keyboard: Any = None) -> None:
            pass

        def getChannel(self, channel: Any) -> Any:  # type: ignore[override]
            return self.channelClass(self, channel)

        def post(self, path: Any, **kwargs: Any) -> Any:
            return True

    USER: dict[str, str | int] = {  # type: ignore[assignment]
        "id": 123456789,
        "first_name": "Harry",
        "last_name": "Potter",
        "username": "harrypotter",
    }

    CHANNEL = {"id": -12345678, "title": "Hogwards", "type": "group"}  # type: ignore[assignment]

    PRIVATE = {"id": 123456789, "type": "private"}

    def patch_send(self) -> None:
        self.sent: list[Any] = []
        self.stickers = 0

        def send_message(chat: Any, message: str, **kwargs: Any) -> dict[str, Any]:
            self.sent.append((chat, message, kwargs))
            return {'message_id': 123}

        self.bot.send_message = send_message  # type: ignore[method-assign]

        def send_sticker(chat: Any, sticker: Any, **kwargs: Any) -> None:
            self.stickers += 1

        self.bot.send_sticker = send_sticker  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        ContactMixin.setUp(self)
        self.contact1 = self.contactClass(
            user=self.USER, channel=self.channelClass(self.bot, self.PRIVATE)
        )
        yield self.contact1.channel.setServiceParent(self.master)

    @defer.inlineCallbacks
    def test_list_notified_events(self) -> InlineCallbacksType[None]:
        self.patch_send()
        channel = telegram.TelegramChannel(self.bot, self.CHANNEL)
        channel.notify_events = {'success'}
        yield channel.list_notified_events()
        self.assertEqual(
            self.sent[0][1], "The following events are being notified:\n🔔 **success**"
        )

    @defer.inlineCallbacks
    def test_list_notified_events_empty(self) -> InlineCallbacksType[None]:
        self.patch_send()
        channel = telegram.TelegramChannel(self.bot, self.CHANNEL)
        channel.notify_events = set()
        yield channel.list_notified_events()
        self.assertEqual(self.sent[0][1], "🔕 No events are being notified.")

    def testDescribeUser(self) -> None:
        self.assertEqual(self.contact1.describeUser(), "Harry Potter (@harrypotter)")

    def testDescribeUserInGroup(self) -> None:
        self.assertEqual(self.contact.describeUser(), "Harry Potter (@harrypotter) on 'Hogwards'")

    @defer.inlineCallbacks
    def test_access_denied(self) -> InlineCallbacksType[None]:
        self.patch_send()
        self.contact1.ACCESS_DENIED_MESSAGES = ["ACCESS DENIED"]
        yield self.contact1.access_denied(tmessage={'message_id': 123})  # type: ignore[func-returns-value]
        self.assertEqual("ACCESS DENIED", self.sent[0][1])

    @defer.inlineCallbacks
    def test_access_denied_group(self) -> InlineCallbacksType[None]:
        self.patch_send()
        self.contact.ACCESS_DENIED_MESSAGES = ["ACCESS DENIED"]  # type: ignore[attr-defined]
        yield self.contact.access_denied(tmessage={'message_id': 123})
        self.assertEqual("ACCESS DENIED", self.sent[0][1])

    def test_query_button_short(self) -> None:
        result = self.contact.query_button("Hello", "hello")  # type: ignore[attr-defined]
        self.assertEqual(result, {'text': "Hello", 'callback_data': "hello"})

    def test_query_button_long(self) -> None:
        payload = 16 * "1234567890"
        key = hash(repr(payload))
        result = self.contact.query_button("Hello", payload)  # type: ignore[attr-defined]
        self.assertEqual(result, {'text': "Hello", 'callback_data': key})
        self.assertEqual(self.bot.query_cache[key], payload)  # type: ignore[attr-defined]

    def test_query_button_non_str(self) -> None:
        payload = {'data': "good"}
        key = hash(repr(payload))
        result = self.contact.query_button("Hello", payload)  # type: ignore[attr-defined]
        self.assertEqual(result, {'text': "Hello", 'callback_data': key})
        self.assertEqual(self.bot.query_cache[key], payload)  # type: ignore[attr-defined]

    def test_query_button_cache(self) -> None:
        payload = 16 * "1234567890"
        key = hash(repr(payload))
        self.bot.query_cache[key] = payload  # type: ignore[attr-defined]
        result = self.contact.query_button("Hello", payload)  # type: ignore[attr-defined]
        self.assertEqual(result, {'text': "Hello", 'callback_data': key})
        self.assertEqual(len(self.bot.query_cache), 1)  # type: ignore[attr-defined]

    def test_query_button_cache_conflict(self) -> None:
        payload = 16 * "1234567890"
        key = hash(repr(payload))
        self.bot.query_cache[key] = "something other"  # type: ignore[attr-defined]
        result = self.contact.query_button("Hello", payload)  # type: ignore[attr-defined]
        self.assertEqual(result, {'text': "Hello", 'callback_data': key + 1})
        self.assertEqual(self.bot.query_cache[key + 1], payload)  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_command_start(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('start', exp_usage=False)
        self.assertEqual(self.sent[0][0], self.CHANNEL['id'])

    @defer.inlineCallbacks
    def test_command_nay(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('nay', contact=self.contact1, tmessage={})

    @defer.inlineCallbacks
    def test_command_nay_reply_markup(self) -> InlineCallbacksType[None]:
        yield self.do_test_command(
            'nay',
            tmessage={
                'reply_to_message': {
                    'message_id': 1234,
                    'reply_markup': {},
                }
            },
        )

    @defer.inlineCallbacks
    def test_commmand_commands(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('commands')
        self.assertEqual(self.sent[0][0], self.CHANNEL['id'])

    @defer.inlineCallbacks
    def test_commmand_commands_botfather(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('commands', 'botfather')
        self.assertEqual(self.sent[0][0], self.CHANNEL['id'])
        self.assertRegex(self.sent[0][1], r"^\w+ - \S+")

    @defer.inlineCallbacks
    def test_command_getid_private(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('getid', contact=self.contact1)
        self.assertEqual(len(self.sent), 1)
        self.assertIn(str(self.USER['id']), self.sent[0][1])

    @defer.inlineCallbacks
    def test_command_getid_group(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('getid')
        self.assertIn(str(self.USER['id']), self.sent[0][1])
        self.assertIn(str(self.CHANNEL['id']), self.sent[1][1])

    def assertButton(self, data: str, pos: tuple[int, int] | None = None, sent: int = 0) -> None:
        keyboard = self.sent[sent][2]['reply_markup']['inline_keyboard']
        if pos is not None:
            r, c = pos
            self.assertEqual(keyboard[r][c]['callback_data'], data)
        else:
            dataset = [b['callback_data'] for row in keyboard for b in row]
            self.assertIn(data, dataset)

    @defer.inlineCallbacks
    def test_command_list(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('list')
        self.assertButton('/list builders')
        self.assertButton('/list workers')
        self.assertButton('/list changes')

    @defer.inlineCallbacks
    def test_command_list_builders(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('list', 'all builders')
        self.assertEqual(len(self.sent), 1)
        for builder in self.BUILDER_NAMES:
            self.assertIn(f'`{builder}` ❌', self.sent[0][1])

    @defer.inlineCallbacks
    def test_command_list_workers(self) -> InlineCallbacksType[None]:
        workers = ['worker1', 'worker2']
        for i, worker in enumerate(workers):
            yield self.master.db.workers.db.insert_test_data([fakedb.Worker(id=i, name=worker)])
        yield self.do_test_command('list', args='all workers')
        self.assertEqual(len(self.sent), 1)
        for worker in workers:
            self.assertIn(f'`{worker}` ❌', self.sent[0][1])

    @defer.inlineCallbacks
    def test_command_list_workers_online(self) -> InlineCallbacksType[None]:
        self.setup_multi_builders()
        # Also set the connectedness:
        yield self.master.db.insert_test_data([
            fakedb.ConnectedWorker(id=113, masterid=13, workerid=1)
        ])
        yield self.do_test_command('list', args='all workers')
        self.assertEqual(len(self.sent), 1)
        self.assertNotIn('`linux1` ⚠️', self.sent[0][1])
        self.assertIn('`linux2` ⚠️', self.sent[0][1])

    @defer.inlineCallbacks
    def test_command_list_changes(self) -> InlineCallbacksType[None]:
        yield self.master.db.workers.db.insert_test_data([
            fakedb.SourceStamp(id=14),
            fakedb.Change(changeid=99, sourcestampid=14),
        ])
        yield self.do_test_command('list', args='2 changes')
        self.assertEqual(len(self.sent), 2)

    @defer.inlineCallbacks
    def test_command_list_changes_long(self) -> InlineCallbacksType[None]:
        yield self.master.db.workers.db.insert_test_data(
            [fakedb.SourceStamp(id=i) for i in range(1, 200)]
            + [fakedb.Change(changeid=i, sourcestampid=i) for i in range(1, 200)]
        )
        yield self.do_test_command('list', args='all changes')
        self.assertIn('reply_markup', self.sent[1][2])

    @defer.inlineCallbacks
    def test_command_watch(self) -> InlineCallbacksType[None]:
        self.setupSomeBuilds()
        yield self.do_test_command('watch')
        self.assertButton('/watch builder1')

    @defer.inlineCallbacks
    def test_command_watch_no_builds(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('watch')

    @defer.inlineCallbacks
    def test_command_stop_no_args(self) -> InlineCallbacksType[None]:
        self.setupSomeBuilds()
        yield self.do_test_command('stop')
        self.assertButton('/stop build builder1')

    @defer.inlineCallbacks
    def test_command_stop_ask_reason(self) -> InlineCallbacksType[None]:
        self.patch_send()
        self.setupSomeBuilds()
        yield self.do_test_command('stop', 'build builder1')
        self.assertIn("give me the reason", self.sent[0][1])
        self.assertEqual(self.contact.template, "/stop build builder1 {}")  # type: ignore[attr-defined]

    def test_ask_reply_group(self) -> None:
        self.patch_send()
        self.contact.ask_for_reply("test")  # type: ignore[attr-defined]
        self.assertEqual(self.sent[0][1], "Ok @harrypotter, now test...")

    def test_ask_reply_group_no_username(self) -> None:
        self.patch_send()
        self.contact.user_info = self.USER.copy()  # type: ignore[attr-defined]
        del self.contact.user_info['username']  # type: ignore[attr-defined]
        self.contact.ask_for_reply("test")  # type: ignore[attr-defined]
        self.assertEqual(self.sent[0][1], "Ok, now reply to this message and test...")

    def test_ask_reply_group_no_username_no_greeting(self) -> None:
        self.patch_send()
        self.contact.user_info = self.USER.copy()  # type: ignore[attr-defined]
        del self.contact.user_info['username']  # type: ignore[attr-defined]
        self.contact.ask_for_reply("test", None)  # type: ignore[attr-defined]
        self.assertEqual(self.sent[0][1], "Reply to this message and test...")

    def test_ask_reply_private_no_greeting(self) -> None:
        self.patch_send()
        self.contact1.ask_for_reply("test", None)  # type: ignore[arg-type]
        self.assertEqual(self.sent[0][1], "Test...")

    @defer.inlineCallbacks
    def test_command_notify_no_args(self) -> InlineCallbacksType[None]:
        self.patch_send()
        self.contact.channel.notify_events = {'success', 'failure'}
        yield self.do_test_command('notify')
        self.assertButton('/notify on-quiet finished')
        self.assertButton('/notify off-quiet success')
        self.assertButton('/notify list')

    @defer.inlineCallbacks
    def test_command_notify_list_with_query(self) -> InlineCallbacksType[None]:
        self.patch_send()

        def delete_message(chat: Any, msg: Any) -> None:
            delete_message.msg = msg  # type: ignore[attr-defined]

        delete_message.msg = None  # type: ignore[attr-defined]
        self.bot.delete_message = delete_message  # type: ignore[attr-defined]

        yield self.do_test_command('notify', 'list', tquery={'message': {'message_id': 2345}})
        self.assertEqual(delete_message.msg, 2345)  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_command_notify_toggle(self) -> InlineCallbacksType[None]:
        self.patch_send()

        def edit_keyboard(chat: Any, msg: Any, keyboard: Any) -> None:
            self.sent.append((chat, None, {'reply_markup': {'inline_keyboard': keyboard}}))

        self.bot.edit_keyboard = edit_keyboard  # type: ignore[attr-defined]

        self.contact.channel.notify_events = {'success', 'failure'}
        yield self.do_test_command(
            'notify', 'on-quiet finished', tquery={'message': {'message_id': 2345}}
        )
        self.assertIn('finished', self.contact.channel.notify_events)
        self.assertButton('/notify off-quiet finished')

    @defer.inlineCallbacks
    def test_command_shutdown(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('shutdown')
        self.assertButton('/shutdown start')
        self.assertButton('/shutdown now')

    @defer.inlineCallbacks
    def test_command_shutdown_shutting_down(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('shutdown', shuttingDown=True)
        self.assertButton('/shutdown stop')
        self.assertButton('/shutdown now')

    def allSchedulers(self) -> Any:
        return self.schedulers

    @defer.inlineCallbacks
    def make_forcescheduler(self, two: bool = False) -> InlineCallbacksType[None]:
        scheduler = forcesched.ForceScheduler(
            name='force1',
            builderNames=['builder1', 'builder2'],
            codebases=[
                forcesched.CodebaseParameter(
                    '',
                    branch=forcesched.StringParameter(name='branch', default="master"),
                    repository=forcesched.FixedParameter(
                        name="repository", default="repository.git"
                    ),
                ),
                forcesched.CodebaseParameter(
                    'second',
                    branch=forcesched.StringParameter(name='branch', default="master"),
                    repository=forcesched.FixedParameter(
                        name="repository", default="repository2.git"
                    ),
                ),
            ],
            reason=forcesched.StringParameter(name='reason', required=True),
        )
        self.schedulers = [scheduler]
        if two:
            scheduler2 = forcesched.ForceScheduler(name='force2', builderNames=['builder2'])
            self.schedulers.append(scheduler2)
        self.bot.master.allSchedulers = self.allSchedulers
        for sched in self.schedulers:
            yield sched.setServiceParent(self.master)

    @defer.inlineCallbacks
    def test_command_force_no_schedulers(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('force', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_noargs_multiple_schedulers(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler(two=True)
        yield self.do_test_command('force')
        self.assertButton('/force force1')
        self.assertButton('/force force2')

    @defer.inlineCallbacks
    def test_command_force_noargs(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force')
        self.assertButton('/force force1 config builder1')
        self.assertButton('/force force1 config builder2')

    @defer.inlineCallbacks
    def test_command_force_only_scheduler(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'force1')
        self.assertButton('/force force1 config builder1')
        self.assertButton('/force force1 config builder2')

    @defer.inlineCallbacks
    def test_command_force_bad_scheduler(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler(two=True)
        yield self.do_test_command('force', 'force3', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_bad_builder(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 config builder0', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_bad_command(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 bad builder1', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_only_bad_command(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'bad builder1', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_config(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 config builder1')
        self.assertButton('/force force1 ask reason builder1 ')
        self.assertButton('/force force1 ask branch builder1 ')
        self.assertButton('/force force1 ask project builder1 ')
        self.assertButton('/force force1 ask revision builder1 ')
        self.assertButton('/force force1 ask second_branch builder1 ')
        self.assertButton('/force force1 ask second_project builder1 ')
        self.assertButton('/force force1 ask second_revision builder1 ')

    @defer.inlineCallbacks
    def test_command_force_config_more(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 config builder1 branch=master')
        self.assertButton('/force force1 ask reason builder1 branch=master')

    @defer.inlineCallbacks
    def test_command_force_config_nothing_missing(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 config builder1 reason=Ok')
        self.assertButton('/force force1 build builder1 reason=Ok')

    @defer.inlineCallbacks
    def test_command_force_ask(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 ask reason builder1 branch=master')
        self.assertEqual(
            self.contact.template,  # type: ignore[attr-defined]
            '/force force1 config builder1 branch=master reason={}',
        )

    @defer.inlineCallbacks
    def test_command_force_build_missing(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 build builder1')
        self.assertButton('/force force1 ask reason builder1 ')

    @defer.inlineCallbacks
    def test_command_force_build(self) -> InlineCallbacksType[None]:
        yield self.make_forcescheduler()

        force_args = {}

        def force(**kwargs: Any) -> None:
            force_args.update(kwargs)

        self.schedulers[0].force = force  # type: ignore[method-assign,assignment]

        yield self.do_test_command('force', 'force1 build builder1 reason=Good')
        self.assertEqual(self.sent[0][1], "Force build successfully requested.")

        expected = {
            'builderid': 23,
            'owner': "Harry Potter (@harrypotter) on 'Hogwards'",
            'reason': 'Good',
            'repository': 'repository.git',  # fixed param
            'second_repository': 'repository2.git',  # fixed param
        }
        self.assertEqual(force_args, expected)


class TestPollingBot(telegram.TelegramPollingBot):
    def __init__(self, updates: int, *args: Any, **kwargs: Any) -> None:
        self.__updates = updates
        super().__init__(*args, **kwargs)

    def process_update(self, update: dict[str, Any]) -> Any:
        self.__updates -= 1
        if not self.__updates:
            self._polling_continue = False
        return super().process_update(update)


class TestTelegramService(TestReactorMixin, unittest.TestCase):
    USER = TestTelegramContact.USER
    CHANNEL = TestTelegramContact.CHANNEL
    PRIVATE = TestTelegramContact.PRIVATE

    URL = 'https://api.telegram.org/bot12345:secret'

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.patch(reactor, 'callLater', self.reactor.callLater)
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)
        self.http = None

    @defer.inlineCallbacks
    def setup_http_service(self) -> InlineCallbacksType[None]:
        self.http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, self.URL
        )

    def setup_http_session(self) -> httpclientservice.HTTPSession:
        return httpclientservice.HTTPSession(self.master.httpservice, self.URL)

    @defer.inlineCallbacks
    def makeBot(
        self, chat_ids: Any = None, authz: Any = None, *args: Any, **kwargs: Any
    ) -> InlineCallbacksType[telegram.TelegramWebhookBot]:
        if chat_ids is None:
            chat_ids = []
        if self.http is None:
            yield self.setup_http_service()
        www = get_plugins('www', None, load_now=True)
        if 'base' not in www:
            raise SkipTest('telegram tests need buildbot-www installed')
        return telegram.TelegramWebhookBot(
            '12345:secret', self.setup_http_session(), chat_ids, authz, *args, **kwargs
        )

    @defer.inlineCallbacks
    def test_getContact(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        c1 = bot.getContact(self.USER, self.PRIVATE)
        c2 = bot.getContact(self.USER, self.CHANNEL)
        c1b = bot.getContact(self.USER, self.PRIVATE)
        self.assertIs(c1, c1b)
        self.assertIsInstance(c2, words.Contact)
        self.assertIn((-12345678, 123456789), bot.contacts)
        self.assertEqual({123456789, -12345678}, set(bot.channels.keys()))

    @defer.inlineCallbacks
    def test_getContact_update(self) -> InlineCallbacksType[None]:
        try:
            bot = yield self.makeBot()
            contact = bot.getContact(self.USER, self.CHANNEL)
            updated_user = self.USER.copy()
            updated_user['username'] = "dirtyharry"
            self.assertEqual(contact.user_info['username'], "harrypotter")
            bot.getContact(updated_user, self.CHANNEL)
            self.assertEqual(contact.user_info['username'], "dirtyharry")
        finally:
            self.USER['username'] = "harrypotter"

    @defer.inlineCallbacks
    def test_getContact_invalid(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        bot.authz = {'': None}

        u = bot.getContact(user=self.USER, channel=self.CHANNEL)
        self.assertNotIn((-12345678, 123456789), bot.contacts)
        self.assertNotIn(-12345678, bot.channels)

        if platform.python_implementation() != 'PyPy':
            py_ver_str = platform.python_version_tuple()[:2]
            py_ver = (int(py_ver_str[0]), int(py_ver_str[1]))
            ref_counts = (2, 3, 2) if py_ver <= (3, 13) else (1, 2, 1)
            self.assertEqual(sys.getrefcount(u), ref_counts[0])  # local, sys
            c = u.channel
            self.assertEqual(sys.getrefcount(c), ref_counts[1])  # local, contact, sys
            del u
            self.assertEqual(sys.getrefcount(c), ref_counts[2])  # local, sys

    @defer.inlineCallbacks
    def test_getContact_valid(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        bot.authz = {'': None, 'command': 123456789}

        bot.getContact(user=self.USER, channel=self.CHANNEL)
        self.assertIn((-12345678, 123456789), bot.contacts)

    @defer.inlineCallbacks
    def test_set_webhook(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        self.http.expect("post", "/setWebhook", json={'url': 'our.webhook'}, content_json={'ok': 1})  # type: ignore[attr-defined]
        yield bot.set_webhook('our.webhook')

    @defer.inlineCallbacks
    def test_set_webhook_cert(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/setWebhook",
            data={'url': 'our.webhook'},
            files={'certificate': b"this is certificate"},
            content_json={'ok': 1},
        )
        yield bot.set_webhook('our.webhook', "this is certificate")

    @defer.inlineCallbacks
    def test_send_message(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/sendMessage",
            json={'chat_id': 1234, 'text': 'Hello', 'parse_mode': 'Markdown'},
            content_json={'ok': 1, 'result': {'message_id': 9876}},
        )
        m = yield bot.send_message(1234, 'Hello')
        self.assertEqual(m['message_id'], 9876)

    @defer.inlineCallbacks
    def test_send_message_long(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()

        text1 = '\n'.join(f"{i + 1:039}" for i in range(102))
        text2 = '\n'.join(f"{i + 1:039}" for i in range(102, 204))
        text3 = '\n'.join(f"{i + 1:039}" for i in range(204, 250))

        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/sendMessage",
            json={
                'chat_id': 1234,
                'text': text1,
                'parse_mode': 'Markdown',
                'reply_to_message_id': 1000,
            },
            content_json={'ok': 1, 'result': {'message_id': 1001}},
        )
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/sendMessage",
            json={'chat_id': 1234, 'text': text2, 'parse_mode': 'Markdown'},
            content_json={'ok': 1, 'result': {'message_id': 1002}},
        )
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/sendMessage",
            json={
                'chat_id': 1234,
                'text': text3,
                'parse_mode': 'Markdown',
                'reply_markup': {'inline_keyboard': 'keyboard'},
            },
            content_json={'ok': 1, 'result': {'message_id': 1003}},
        )

        text = '\n'.join(f"{i + 1:039}" for i in range(250))
        m = yield bot.send_message(
            1234, text, reply_markup={'inline_keyboard': 'keyboard'}, reply_to_message_id=1000
        )
        self.assertEqual(m['message_id'], 1003)

    @defer.inlineCallbacks
    def test_edit_message(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/editMessageText",
            json={'chat_id': 1234, 'message_id': 9876, 'text': 'Hello', 'parse_mode': 'Markdown'},
            content_json={'ok': 1, 'result': {'message_id': 9876}},
        )
        m = yield bot.edit_message(1234, 9876, 'Hello')
        self.assertEqual(m['message_id'], 9876)

    @defer.inlineCallbacks
    def test_delete_message(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/deleteMessage",
            json={'chat_id': 1234, 'message_id': 9876},
            content_json={'ok': 1},
        )
        yield bot.delete_message(1234, 9876)

    @defer.inlineCallbacks
    def test_send_sticker(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/sendSticker",
            json={'chat_id': 1234, 'sticker': 'xxxxx'},
            content_json={'ok': 1, 'result': {'message_id': 9876}},
        )
        m = yield bot.send_sticker(1234, 'xxxxx')
        self.assertEqual(m['message_id'], 9876)

    @defer.inlineCallbacks
    def test_set_nickname(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        self.assertIsNone(bot.nickname)
        self.http.expect(  # type: ignore[attr-defined]
            "post", "/getMe", content_json={'ok': 1, 'result': {'username': 'testbot'}}
        )
        yield bot.set_nickname()
        self.assertEqual(bot.nickname, 'testbot')

    def prepare_request(self, **kwargs: Any) -> FakeRequest:
        payload = {"update_id": 12345}
        payload.update(kwargs)
        content = unicode2bytes(json.dumps(payload))
        request = FakeRequest(content=content)
        request.uri = b"/bot12345:secret"
        request.method = b"POST"
        request.received_headers[b'Content-Type'] = b"application/json"  # type: ignore[index,assignment]
        return request

    def request_message(self, text: str) -> FakeRequest:
        return self.prepare_request(
            message={
                "message_id": 123,
                "from": self.USER,
                "chat": self.CHANNEL,
                "date": 1566688888,
                "text": text,
            }
        )

    def request_query(self, data: str) -> FakeRequest:
        return self.prepare_request(
            callback_query={
                "id": 123456,
                "from": self.USER,
                "data": data,
                "message": {
                    "message_id": 12345,
                    "from": self.USER,
                    "chat": self.CHANNEL,
                    "date": 1566688888,
                },
            }
        )

    @defer.inlineCallbacks
    def test_get_update(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        request = self.request_message("test")
        update = bot.get_update(request)
        self.assertEqual(update['message']['from'], self.USER)
        self.assertEqual(update['message']['chat'], self.CHANNEL)

    @defer.inlineCallbacks
    def test_get_update_bad_content_type(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        request = self.request_message("test")
        request.received_headers[b'Content-Type'] = b"application/data"  # type: ignore[index,assignment]
        with self.assertRaises(ValueError):
            bot.get_update(request)

    @defer.inlineCallbacks
    def test_render_POST(self) -> InlineCallbacksType[None]:
        # This actually also tests process_incoming
        bot = yield self.makeBot()
        bot.contactClass = FakeContact
        request = self.request_message("test")
        bot.webhook.render_POST(request)
        contact = bot.getContact(self.USER, self.CHANNEL)
        self.assertEqual(contact.messages, ["test"])

    @defer.inlineCallbacks
    def test_parse_query_cached(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        bot.contactClass = FakeContact
        bot.query_cache.update({100: "good"})
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/answerCallbackQuery",
            json={'callback_query_id': 123456},
            content_json={'ok': 1},
        )
        request = self.request_query("100")
        bot.process_webhook(request)
        self.assertEqual(bot.getContact(self.USER, self.CHANNEL).messages, ["good"])

    @defer.inlineCallbacks
    def test_parse_query_cached_dict(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        bot.contactClass = FakeContact
        bot.query_cache = {100: {'command': "good", 'notify': "hello"}}
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/answerCallbackQuery",
            json={'callback_query_id': 123456, 'text': "hello"},
            content_json={'ok': 1},
        )
        request = self.request_query("100")
        bot.process_webhook(request)
        self.assertEqual(bot.getContact(self.USER, self.CHANNEL).messages, ["good"])

    @defer.inlineCallbacks
    def test_parse_query_explicit(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        bot.contactClass = FakeContact
        bot.query_cache = {100: "bad"}
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/answerCallbackQuery",
            json={'callback_query_id': 123456},
            content_json={'ok': 1},
        )
        request = self.request_query("good")
        bot.process_webhook(request)
        self.assertEqual(bot.getContact(self.USER, self.CHANNEL).messages, ["good"])

    @defer.inlineCallbacks
    def test_parse_query_bad(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        bot.contactClass = FakeContact
        bot.query_cache.update({100: "bad"})
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/editMessageReplyMarkup",
            json={'chat_id': -12345678, 'message_id': 12345},
            content_json={'ok': 1},
        )
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/answerCallbackQuery",
            json={'callback_query_id': 123456, 'text': "Sorry, button is no longer valid!"},
            content_json={'ok': 1},
        )
        request = self.request_query("101")
        bot.process_webhook(request)

    def makePollingBot(
        self, updates: int, chat_ids: Any = None, authz: Any = None, *args: Any, **kwargs: Any
    ) -> TestPollingBot:
        if chat_ids is None:
            chat_ids = []

        return TestPollingBot(
            updates, '12345:secret', self.setup_http_session(), chat_ids, authz, *args, **kwargs
        )

    @defer.inlineCallbacks
    def test_polling(self) -> InlineCallbacksType[None]:
        yield self.setup_http_service()
        bot = self.makePollingBot(2)
        bot._polling_continue = True
        self.http.expect("post", "/deleteWebhook", content_json={"ok": 1})  # type: ignore[attr-defined]
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/getUpdates",
            json={'timeout': bot.poll_timeout},
            content_json={
                'ok': 1,
                'result': [
                    {
                        "update_id": 10000,
                        "message": {
                            "message_id": 123,
                            "from": self.USER,
                            "chat": self.CHANNEL,
                            "date": 1566688888,
                            "text": "ignore",
                        },
                    }
                ],
            },
        )
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/getUpdates",
            json={'timeout': bot.poll_timeout, "offset": 10001},
            content_json={
                'ok': 1,
                'result': [
                    {
                        "update_id": 10001,
                        "message": {
                            "message_id": 124,
                            "from": self.USER,
                            "chat": self.CHANNEL,
                            "date": 1566688889,
                            "text": "/nay",
                        },
                    }
                ],
            },
        )
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/sendMessage",
            json={'chat_id': -12345678, 'text': 'Never mind, Harry...', 'parse_mode': 'Markdown'},
            content_json={'ok': 1, 'result': {'message_id': 125}},
        )
        yield bot.do_polling()

    @defer.inlineCallbacks
    def test_format_build_status(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        build = {'results': SUCCESS}
        self.assertEqual(bot.format_build_status(build), "completed successfully ✅")

    @defer.inlineCallbacks
    def test_format_build_status_short(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        build = {'results': WARNINGS}
        self.assertEqual(bot.format_build_status(build, short=True), " ⚠️")

    class HttpServiceWithErrors(fakehttpclientservice.HTTPClientService):
        def __init__(self, skip: int, errs: int, *args: Any, **kwargs: Any) -> None:
            self.__skip = skip
            self.__errs = errs
            self.succeeded = False
            super().__init__(*args, **kwargs)

        def _do_request(  # type: ignore[override]
            self, session: httpclientservice.HTTPSession, method: str, ep: str, **kwargs: Any
        ) -> Any:
            if method == 'post':
                if self.__skip:
                    self.__skip -= 1
                else:
                    if self.__errs:
                        self.__errs -= 1
                        raise RuntimeError(f"{self.__errs + 1}")
                    self.succeeded = True
            return super()._do_request(session, method, ep, **kwargs)

    # returns a Deferred
    @defer.inlineCallbacks
    def setup_http_service_with_errors(self, skip: int, errs: int) -> InlineCallbacksType[None]:
        url = 'https://api.telegram.org/bot12345:secret'
        self.http = yield self.HttpServiceWithErrors.getService(self.master, self, skip, errs, url)

    @defer.inlineCallbacks
    def test_post_not_ok(self) -> InlineCallbacksType[None]:
        bot = yield self.makeBot()
        self.http.expect("post", "/post", content_json={'ok': 0})  # type: ignore[attr-defined]

        def log(msg: str, source: Any = None) -> None:
            logs.append(msg)

        logs: list[str] = []
        bot.log = log

        yield bot.post("/post")
        self.assertIn("ERROR", logs[0])

    @defer.inlineCallbacks
    def test_post_need_repeat(self) -> InlineCallbacksType[None]:
        yield self.setup_http_service_with_errors(0, 2)
        bot = yield self.makeBot()
        self.http.expect("post", "/post", content_json={'ok': 1})  # type: ignore[attr-defined]

        def log(msg: str, source: Any = None) -> None:
            logs.append(msg)

        logs: list[str] = []
        bot.log = log

        bot.post("/post")
        self.assertIn("ERROR", logs[0])

        self.reactor.pump(3 * [30.0])

        self.assertTrue(self.http.succeeded)  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_polling_need_repeat(self) -> InlineCallbacksType[None]:
        yield self.setup_http_service_with_errors(1, 2)
        bot = self.makePollingBot(1)
        bot.reactor = self.reactor  # type: ignore[attr-defined]
        bot._polling_continue = True
        self.http.expect("post", "/deleteWebhook", content_json={"ok": 1})  # type: ignore[attr-defined]
        self.http.expect(  # type: ignore[attr-defined]
            "post",
            "/getUpdates",
            json={'timeout': bot.poll_timeout},
            content_json={
                'ok': 1,
                'result': [
                    {
                        "update_id": 10000,
                        "message": {
                            "message_id": 123,
                            "from": self.USER,
                            "chat": self.CHANNEL,
                            "date": 1566688888,
                            "text": "ignore",
                        },
                    }
                ],
            },
        )

        def log(msg: str, source: Any = None) -> None:
            logs.append(msg)

        logs: list[str] = []
        bot.log = log  # type: ignore[method-assign]

        bot.do_polling()
        self.assertIn("ERROR", logs[0])

        self.reactor.pump(3 * [30.0])

        self.assertTrue(self.http.succeeded)  # type: ignore[attr-defined]
