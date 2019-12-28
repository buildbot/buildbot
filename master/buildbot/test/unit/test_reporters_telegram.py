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

import json
import sys

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import telegram
from buildbot.reporters import words
from buildbot.schedulers import forcesched
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.web import FakeRequest
from buildbot.test.unit.test_reporters_words import ContactMixin
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import service
from buildbot.util import unicode2bytes


class FakeChannel(service.AsyncService):
    pass


class FakeContact:

    def __init__(self, user=None, channel=None):
        super().__init__()
        self.user_id = user['id']
        self.user_info = user
        self.channel = FakeChannel
        self.channel.chat_info = channel.chat_info
        self.template = None
        self.messages = []

    def handleMessage(self, message, **kwargs):
        self.messages.append(message)
        return defer.succeed(message)


class TestTelegramContact(ContactMixin, unittest.TestCase):
    channelClass = telegram.TelegramChannel
    contactClass = telegram.TelegramContact

    class botClass(words.StatusBot):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.query_cache = {}

        def send_message(self, chat, message, **kwargs):
            return {'message_id': 123}

        def edit_message(bot, chat, msgid, message, **kwargs):
            return {'message_id': 123}

        def delete_message(bot, chat, msgid):
            pass

        def send_sticker(bot, chat, sticker, **kwargs):
            pass

        def edit_keyboard(self, chat, msg, keyboard=None):
            pass

        def getChannel(self, channel):
            return self.channelClass(self, channel)

    USER = {
        "id": 123456789,
        "first_name": "Harry",
        "last_name": "Potter",
        "username": "harrypotter",
    }

    CHANNEL = {
        "id": -12345678,
        "title": "Hogwards",
        "type": "group"
    }

    PRIVATE = {
        "id": 123456789,
        "type": "private"
    }

    def patch_send(self):
        self.sent = []
        self.stickers = 0

        def send_message(chat, message, **kwargs):
            self.sent.append((chat, message, kwargs))
            return {'message_id': 123}
        self.bot.send_message = send_message

        def send_sticker(chat, sticker, **kwargs):
            self.stickers += 1
        self.bot.send_sticker = send_sticker

    @defer.inlineCallbacks
    def setUp(self):
        ContactMixin.setUp(self)
        self.contact1 = self.contactClass(user=self.USER, channel=self.channelClass(self.bot, self.PRIVATE))
        yield self.contact1.channel.setServiceParent(self.master)

    @defer.inlineCallbacks
    def test_list_notified_events(self):
        self.patch_send()
        channel = telegram.TelegramChannel(self.bot, self.CHANNEL)
        channel.notify_events = {'success'}
        yield channel.list_notified_events()
        self.assertEquals(self.sent[0][1], "The following events are being notified:\n🔔 **success**")

    @defer.inlineCallbacks
    def test_list_notified_events_empty(self):
        self.patch_send()
        channel = telegram.TelegramChannel(self.bot, self.CHANNEL)
        channel.notify_events = set()
        yield channel.list_notified_events()
        self.assertEquals(self.sent[0][1], "🔕 No events are being notified.")

    def testDescribeUser(self):
        self.assertEquals(self.contact1.describeUser(), "Harry Potter (@harrypotter)")

    def testDescribeUserInGroup(self):
        self.assertEquals(self.contact.describeUser(), "Harry Potter (@harrypotter) on 'Hogwards'")

    @defer.inlineCallbacks
    def test_access_denied(self):
        self.patch_send()
        self.contact1.ACCESS_DENIED_MESSAGES = ["ACCESS DENIED"]
        yield self.contact1.access_denied(tmessage={'message_id': 123})
        self.assertEqual("ACCESS DENIED", self.sent[0][1])

    @defer.inlineCallbacks
    def test_access_denied_group(self):
        self.patch_send()
        self.contact.ACCESS_DENIED_MESSAGES = ["ACCESS DENIED"]
        yield self.contact.access_denied(tmessage={'message_id': 123})
        self.assertEqual("ACCESS DENIED", self.sent[0][1])

    def test_query_button_short(self):
        result = self.contact.query_button("Hello", "hello")
        self.assertEquals(result, {'text': "Hello", 'callback_data': "hello"})

    def test_query_button_long(self):
        payload = 16 * "1234567890"
        key = hash(repr(payload))
        result = self.contact.query_button("Hello", payload)
        self.assertEquals(result, {'text': "Hello", 'callback_data': key})
        self.assertEquals(self.bot.query_cache[key], payload)

    def test_query_button_non_str(self):
        payload = {'data': "good"}
        key = hash(repr(payload))
        result = self.contact.query_button("Hello", payload)
        self.assertEquals(result, {'text': "Hello", 'callback_data': key})
        self.assertEquals(self.bot.query_cache[key], payload)

    def test_query_button_cache(self):
        payload = 16 * "1234567890"
        key = hash(repr(payload))
        self.bot.query_cache[key] = payload
        result = self.contact.query_button("Hello", payload)
        self.assertEquals(result, {'text': "Hello", 'callback_data': key})
        self.assertEquals(len(self.bot.query_cache), 1)

    def test_query_button_cache_conflict(self):
        payload = 16 * "1234567890"
        key = hash(repr(payload))
        self.bot.query_cache[key] = "something other"
        result = self.contact.query_button("Hello", payload)
        self.assertEquals(result, {'text': "Hello", 'callback_data': key + 1})
        self.assertEquals(self.bot.query_cache[key + 1], payload)

    @defer.inlineCallbacks
    def test_command_start(self):
        yield self.do_test_command('start', exp_usage=False)
        self.assertEqual(self.sent[0][0], self.CHANNEL['id'])

    @defer.inlineCallbacks
    def test_command_nay(self):
        yield self.do_test_command('nay', contact=self.contact1, tmessage={})

    @defer.inlineCallbacks
    def test_command_nay_reply_markup(self):
        yield self.do_test_command('nay', tmessage={
            'reply_to_message': {
                'message_id': 1234,
                'reply_markup': {},
            }})

    @defer.inlineCallbacks
    def test_commmand_commands(self):
        yield self.do_test_command('commands')
        self.assertEqual(self.sent[0][0], self.CHANNEL['id'])

    @defer.inlineCallbacks
    def test_commmand_commands_botfather(self):
        yield self.do_test_command('commands', 'botfather')
        self.assertEqual(self.sent[0][0], self.CHANNEL['id'])
        self.assertRegex(self.sent[0][1], r"^\w+ - \S+")

    @defer.inlineCallbacks
    def test_command_getid_private(self):
        yield self.do_test_command('getid', contact=self.contact1)
        self.assertEqual(len(self.sent), 1)
        self.assertIn(str(self.USER['id']), self.sent[0][1])

    @defer.inlineCallbacks
    def test_command_getid_group(self):
        yield self.do_test_command('getid')
        self.assertIn(str(self.USER['id']), self.sent[0][1])
        self.assertIn(str(self.CHANNEL['id']), self.sent[1][1])

    def assertButton(self, data, pos=None, sent=0):
        keyboard = self.sent[sent][2]['reply_markup']['inline_keyboard']
        if pos is not None:
            r, c = pos
            self.assertEquals(keyboard[r][c]['callback_data'], data)
        else:
            dataset = [b['callback_data'] for row in keyboard for b in row]
            self.assertIn(data, dataset)

    @defer.inlineCallbacks
    def test_command_list(self):
        yield self.do_test_command('list')
        self.assertButton('/list builders')
        self.assertButton('/list workers')
        self.assertButton('/list changes')

    @defer.inlineCallbacks
    def test_command_list_builders(self):
        yield self.do_test_command('list', 'all builders')
        self.assertEqual(len(self.sent), 1)
        for builder in self.BUILDER_NAMES:
            self.assertIn('`%s` ❌' % builder, self.sent[0][1])

    @defer.inlineCallbacks
    def test_command_list_workers(self):
        workers = ['worker1', 'worker2']
        for worker in workers:
            self.master.db.workers.db.insertTestData([
                fakedb.Worker(name=worker)
            ])
        yield self.do_test_command('list', args='all workers')
        self.assertEqual(len(self.sent), 1)
        for worker in workers:
            self.assertIn('`%s` ❌' % worker, self.sent[0][1])

    @defer.inlineCallbacks
    def test_command_list_workers_online(self):
        self.setup_multi_builders()
        # Also set the connectedness:
        self.master.db.insertTestData([
            fakedb.ConnectedWorker(id=113, masterid=13, workerid=1)
        ])
        yield self.do_test_command('list', args='all workers')
        self.assertEqual(len(self.sent), 1)
        self.assertNotIn('`linux1` ⚠️', self.sent[0][1])
        self.assertIn('`linux2` ⚠️', self.sent[0][1])

    @defer.inlineCallbacks
    def test_command_list_changes(self):
        self.master.db.workers.db.insertTestData([
            fakedb.Change()
        ])
        yield self.do_test_command('list', args='2 changes')
        self.assertEqual(len(self.sent), 2)

    @defer.inlineCallbacks
    def test_command_list_changes_long(self):
        self.master.db.workers.db.insertTestData([
            fakedb.Change() for i in range(200)
        ])
        yield self.do_test_command('list', args='all changes')
        self.assertIn('reply_markup', self.sent[1][2])

    @defer.inlineCallbacks
    def test_command_watch(self):
        self.setupSomeBuilds()
        yield self.do_test_command('watch')
        self.assertButton('/watch builder1')

    @defer.inlineCallbacks
    def test_command_watch_no_builds(self):
        yield self.do_test_command('watch')

    @defer.inlineCallbacks
    def test_command_stop_no_args(self):
        self.setupSomeBuilds()
        yield self.do_test_command('stop')
        self.assertButton('/stop build builder1')

    @defer.inlineCallbacks
    def test_command_stop_ask_reason(self):
        self.patch_send()
        self.setupSomeBuilds()
        yield self.do_test_command('stop', 'build builder1')
        self.assertIn("give me the reason", self.sent[0][1])
        self.assertEquals(self.contact.template, "/stop build builder1 {}")

    def test_ask_reply_group(self):
        self.patch_send()
        self.contact.ask_for_reply("test")
        self.assertEqual(self.sent[0][1], "Ok @harrypotter, now test...")

    def test_ask_reply_group_no_username(self):
        self.patch_send()
        self.contact.user_info = self.USER.copy()
        del self.contact.user_info['username']
        self.contact.ask_for_reply("test")
        self.assertEqual(self.sent[0][1], "Ok, now reply to this message and test...")

    def test_ask_reply_group_no_username_no_greeting(self):
        self.patch_send()
        self.contact.user_info = self.USER.copy()
        del self.contact.user_info['username']
        self.contact.ask_for_reply("test", None)
        self.assertEqual(self.sent[0][1], "Reply to this message and test...")

    def test_ask_reply_private_no_greeting(self):
        self.patch_send()
        self.contact1.ask_for_reply("test", None)
        self.assertEqual(self.sent[0][1], "Test...")

    @defer.inlineCallbacks
    def test_command_notify_no_args(self):
        self.patch_send()
        self.contact.channel.notify_events = {'success', 'failure'}
        yield self.do_test_command('notify')
        self.assertButton('/notify on-quiet finished')
        self.assertButton('/notify off-quiet success')
        self.assertButton('/notify list')

    @defer.inlineCallbacks
    def test_command_notify_list_with_query(self):
        self.patch_send()

        def delete_message(chat, msg):
            delete_message.msg = msg
        delete_message.msg = None
        self.bot.delete_message = delete_message

        yield self.do_test_command('notify', 'list', tquery={
            'message': {'message_id': 2345}
        })
        self.assertEqual(delete_message.msg, 2345)

    @defer.inlineCallbacks
    def test_command_notify_toggle(self):
        self.patch_send()

        def edit_keyboard(chat, msg, keyboard):
            self.sent.append((chat, None, {
                'reply_markup': {'inline_keyboard': keyboard}}))
        self.bot.edit_keyboard = edit_keyboard

        self.contact.channel.notify_events = {'success', 'failure'}
        yield self.do_test_command('notify', 'on-quiet finished', tquery={
            'message': {'message_id': 2345}
        })
        self.assertIn('finished', self.contact.channel.notify_events)
        self.assertButton('/notify off-quiet finished')

    @defer.inlineCallbacks
    def test_command_shutdown(self):
        yield self.do_test_command('shutdown')
        self.assertButton('/shutdown start')
        self.assertButton('/shutdown now')

    @defer.inlineCallbacks
    def test_command_shutdown_shutting_down(self):
        yield self.do_test_command('shutdown', shuttingDown=True)
        self.assertButton('/shutdown stop')
        self.assertButton('/shutdown now')

    def allSchedulers(self):
        return self.schedulers

    def make_forcescheduler(self, two=False):
        scheduler = forcesched.ForceScheduler(
            name='force1',
            builderNames=['builder1', 'builder2'],
            codebases=[
                forcesched.CodebaseParameter('',
                    branch=forcesched.StringParameter(
                        name='branch',
                        default="master"),
                    repository=forcesched.FixedParameter(
                        name="repository",
                        default="repository.git")),
                forcesched.CodebaseParameter('second',
                    branch=forcesched.StringParameter(
                        name='branch',
                        default="master"),
                    repository=forcesched.FixedParameter(
                        name="repository",
                        default="repository2.git"))],
            reason=forcesched.StringParameter(
                name='reason',
                required=True))
        self.schedulers = [scheduler]
        if two:
            scheduler2 = forcesched.ForceScheduler(
                name='force2',
                builderNames=['builder2'])
            self.schedulers.append(scheduler2)
        self.bot.master.allSchedulers = self.allSchedulers

    @defer.inlineCallbacks
    def test_command_force_no_schedulers(self):
        yield self.do_test_command('force', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_noargs_multiple_schedulers(self):
        self.make_forcescheduler(two=True)
        yield self.do_test_command('force')
        self.assertButton('/force force1')
        self.assertButton('/force force2')

    @defer.inlineCallbacks
    def test_command_force_noargs(self):
        self.make_forcescheduler()
        yield self.do_test_command('force')
        self.assertButton('/force force1 config builder1')
        self.assertButton('/force force1 config builder2')

    @defer.inlineCallbacks
    def test_command_force_only_scheduler(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'force1')
        self.assertButton('/force force1 config builder1')
        self.assertButton('/force force1 config builder2')

    @defer.inlineCallbacks
    def test_command_force_bad_scheduler(self):
        self.make_forcescheduler(two=True)
        yield self.do_test_command('force', 'force3', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_bad_builder(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 config builder0', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_bad_command(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 bad builder1', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_only_bad_command(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'bad builder1', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_config(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 config builder1')
        self.assertButton('/force force1 ask reason builder1 ')
        self.assertButton('/force force1 ask branch builder1 ')
        self.assertButton('/force force1 ask project builder1 ')
        self.assertButton('/force force1 ask revision builder1 ')
        self.assertButton('/force force1 ask second_branch builder1 ')
        self.assertButton('/force force1 ask second_project builder1 ')
        self.assertButton('/force force1 ask second_revision builder1 ')

    @defer.inlineCallbacks
    def test_command_force_config_more(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 config builder1 branch=master')
        self.assertButton('/force force1 ask reason builder1 branch=master')

    @defer.inlineCallbacks
    def test_command_force_config_nothing_missing(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 config builder1 reason=Ok')
        self.assertButton('/force force1 build builder1 reason=Ok')

    @defer.inlineCallbacks
    def test_command_force_ask(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 ask reason builder1 branch=master')
        self.assertEqual(self.contact.template,
                         '/force force1 config builder1 branch=master reason={}')

    @defer.inlineCallbacks
    def test_command_force_build_missing(self):
        self.make_forcescheduler()
        yield self.do_test_command('force', 'force1 build builder1')
        self.assertButton('/force force1 ask reason builder1 ')

    @defer.inlineCallbacks
    def test_command_force_build(self):
        self.make_forcescheduler()

        force_args = {}

        def force(**kwargs):
            force_args.update(kwargs)
        self.schedulers[0].force = force

        yield self.do_test_command('force', 'force1 build builder1 reason=Good')
        self.assertEqual(self.sent[0][1], "Force build successfully requested.")

        expected = {
            'builderid': 23,
            'owner': "Harry Potter (@harrypotter) on 'Hogwards'",
            'reason': 'Good',
            'repository': 'repository.git',         # fixed param
            'second_repository': 'repository2.git'  # fixed param
        }
        self.assertEqual(force_args, expected)


class TestPollingBot(telegram.TelegramPollingBot):

    def __init__(self, updates, *args, **kwargs):
        self.__updates = updates
        super().__init__(*args, **kwargs)

    def process_update(self, update):
        self.__updates -= 1
        if not self.__updates:
            self._polling_continue = False
        return super().process_update(update)


class TestTelegramService(TestReactorMixin, unittest.TestCase):

    USER = TestTelegramContact.USER
    CHANNEL = TestTelegramContact.CHANNEL
    PRIVATE = TestTelegramContact.PRIVATE

    def setUp(self):
        self.setUpTestReactor()
        self.patch(reactor, 'callLater', self.reactor.callLater)
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    def setupFakeHttp(self):
        return self.successResultOf(fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://api.telegram.org/bot12345:secret'))

    def makeBot(self, chat_ids=None, authz=None, *args, **kwargs):
        if chat_ids is None:
            chat_ids = []
        http = self.setupFakeHttp()
        return telegram.TelegramWebhookBot('12345:secret', http, chat_ids, authz, *args, **kwargs)

    def test_getContact(self):
        bot = self.makeBot()
        c1 = bot.getContact(self.USER, self.PRIVATE)
        c2 = bot.getContact(self.USER, self.CHANNEL)
        c1b = bot.getContact(self.USER, self.PRIVATE)
        self.assertIs(c1, c1b)
        self.assertIsInstance(c2, words.Contact)
        self.assertIn((-12345678, 123456789), bot.contacts)
        self.assertEqual({123456789, -12345678}, set(bot.channels.keys()))

    def test_getContact_update(self):
        try:
            bot = self.makeBot()
            contact = bot.getContact(self.USER, self.CHANNEL)
            updated_user = self.USER.copy()
            updated_user['username'] = "dirtyharry"
            self.assertEquals(contact.user_info['username'], "harrypotter")
            bot.getContact(updated_user, self.CHANNEL)
            self.assertEquals(contact.user_info['username'], "dirtyharry")
        finally:
            self.USER['username'] = "harrypotter"

    def test_getContact_invalid(self):
        bot = self.makeBot()
        bot.authz = {'': None}

        u = bot.getContact(user=self.USER, channel=self.CHANNEL)
        self.assertNotIn((-12345678, 123456789), bot.contacts)
        self.assertNotIn(-12345678, bot.channels)

        self.assertEqual(sys.getrefcount(u), 2)  # local, sys
        c = u.channel
        self.assertEqual(sys.getrefcount(c), 3)  # local, contact, sys
        del u
        self.assertEqual(sys.getrefcount(c), 2)  # local, sys

    def test_getContact_valid(self):
        bot = self.makeBot()
        bot.authz = {'': None, 'command': 123456789}

        bot.getContact(user=self.USER, channel=self.CHANNEL)
        self.assertIn((-12345678, 123456789), bot.contacts)

    @defer.inlineCallbacks
    def test_set_webhook(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/setWebhook",
                               json={'url': 'our.webhook'},
                               content_json={'ok': 1})
        yield bot.set_webhook('our.webhook')

    @defer.inlineCallbacks
    def test_set_webhook_cert(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/setWebhook",
                               data={'url': 'our.webhook'},
                               files={'certificate': b"this is certificate"},
                               content_json={'ok': 1})
        yield bot.set_webhook('our.webhook', "this is certificate")

    @defer.inlineCallbacks
    def test_send_message(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/sendMessage",
                               json={'chat_id': 1234, 'text': 'Hello',
                                     'parse_mode': 'Markdown'},
                               content_json={'ok': 1, 'result': {'message_id': 9876}})
        m = yield bot.send_message(1234, 'Hello')
        self.assertEqual(m['message_id'], 9876)

    @defer.inlineCallbacks
    def test_send_message_long(self):
        bot = self.makeBot()

        text1 = '\n'.join("{:039d}".format(i + 1) for i in range(102))
        text2 = '\n'.join("{:039d}".format(i + 1) for i in range(102, 204))
        text3 = '\n'.join("{:039d}".format(i + 1) for i in range(204, 250))

        bot.http_client.expect("post", "/sendMessage",
                               json={'chat_id': 1234, 'text': text1,
                                     'parse_mode': 'Markdown',
                                     'reply_to_message_id': 1000},
                               content_json={'ok': 1, 'result': {'message_id': 1001}})
        bot.http_client.expect("post", "/sendMessage",
                               json={'chat_id': 1234, 'text': text2,
                                     'parse_mode': 'Markdown'},
                               content_json={'ok': 1, 'result': {'message_id': 1002}})
        bot.http_client.expect("post", "/sendMessage",
                               json={'chat_id': 1234, 'text': text3,
                                     'parse_mode': 'Markdown',
                                     'reply_markup': {'inline_keyboard': 'keyboard'}},
                               content_json={'ok': 1, 'result': {'message_id': 1003}})

        text = '\n'.join("{:039d}".format(i + 1) for i in range(250))
        m = yield bot.send_message(1234, text,
                                   reply_markup={'inline_keyboard': 'keyboard'},
                                   reply_to_message_id=1000)
        self.assertEqual(m['message_id'], 1003)

    @defer.inlineCallbacks
    def test_edit_message(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/editMessageText",
                               json={'chat_id': 1234, 'message_id': 9876, 'text': 'Hello',
                                     'parse_mode': 'Markdown'},
                               content_json={'ok': 1, 'result': {'message_id': 9876}})
        m = yield bot.edit_message(1234, 9876, 'Hello')
        self.assertEqual(m['message_id'], 9876)

    @defer.inlineCallbacks
    def test_delete_message(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/deleteMessage",
                               json={'chat_id': 1234, 'message_id': 9876},
                               content_json={'ok': 1})
        yield bot.delete_message(1234, 9876)

    @defer.inlineCallbacks
    def test_send_sticker(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/sendSticker",
                               json={'chat_id': 1234, 'sticker': 'xxxxx'},
                               content_json={'ok': 1, 'result': {'message_id': 9876}})
        m = yield bot.send_sticker(1234, 'xxxxx')
        self.assertEqual(m['message_id'], 9876)

    @defer.inlineCallbacks
    def test_set_nickname(self):
        bot = self.makeBot()
        self.assertIsNone(bot.nickname)
        bot.http_client.expect("post", "/getMe",
                               content_json={'ok': 1, 'result': {'username': 'testbot'}})
        yield bot.set_nickname()
        self.assertEqual(bot.nickname, 'testbot')

    def prepare_request(self, **kwargs):
        payload = {"update_id": 12345}
        payload.update(kwargs)
        content = unicode2bytes(json.dumps(payload))
        request = FakeRequest(content=content)
        request.uri = b"/bot12345:secret"
        request.method = b"POST"
        request.received_headers[b'Content-Type'] = b"application/json"
        return request

    def request_message(self, text):
        return self.prepare_request(message={
            "message_id": 123,
            "from": self.USER,
            "chat": self.CHANNEL,
            "date": 1566688888,
            "text": text,
        })

    def request_query(self, data):
        return self.prepare_request(callback_query={
            "id": 123456,
            "from": self.USER,
            "data": data,
            "message": {
                "message_id": 12345,
                "from": self.USER,
                "chat": self.CHANNEL,
                "date": 1566688888,
        }})

    def test_get_update(self):
        bot = self.makeBot()
        request = self.request_message("test")
        update = bot.get_update(request)
        self.assertEquals(update['message']['from'], self.USER)
        self.assertEquals(update['message']['chat'], self.CHANNEL)

    def test_get_update_bad_content_type(self):
        bot = self.makeBot()
        request = self.request_message("test")
        request.received_headers[b'Content-Type'] = b"application/data"
        with self.assertRaises(ValueError):
            bot.get_update(request)

    def test_render_POST(self):
        # This actually also tests process_incoming
        bot = self.makeBot()
        bot.contactClass = FakeContact
        request = self.request_message("test")
        bot.webhook.render_POST(request)
        contact = bot.getContact(self.USER, self.CHANNEL)
        self.assertEquals(contact.messages, ["test"])

    def test_parse_query_cached(self):
        bot = self.makeBot()
        bot.contactClass = FakeContact
        bot.query_cache.update({
            100: "good"
        })
        bot.http_client.expect("post", "/answerCallbackQuery",
                               json={'callback_query_id': 123456},
                               content_json={'ok': 1})
        request = self.request_query("100")
        bot.process_webhook(request)
        self.assertEquals(bot.getContact(self.USER, self.CHANNEL).messages, ["good"])

    def test_parse_query_cached_dict(self):
        bot = self.makeBot()
        bot.contactClass = FakeContact
        bot.query_cache = {
            100: {'command': "good", 'notify': "hello"}
        }
        bot.http_client.expect("post", "/answerCallbackQuery",
                               json={'callback_query_id': 123456, 'text': "hello"},
                               content_json={'ok': 1})
        request = self.request_query("100")
        bot.process_webhook(request)
        self.assertEquals(bot.getContact(self.USER, self.CHANNEL).messages, ["good"])

    def test_parse_query_explicit(self):
        bot = self.makeBot()
        bot.contactClass = FakeContact
        bot.query_cache = {
            100: "bad"
        }
        bot.http_client.expect("post", "/answerCallbackQuery",
                               json={'callback_query_id': 123456},
                               content_json={'ok': 1})
        request = self.request_query("good")
        bot.process_webhook(request)
        self.assertEquals(bot.getContact(self.USER, self.CHANNEL).messages, ["good"])

    def test_parse_query_bad(self):
        bot = self.makeBot()
        bot.contactClass = FakeContact
        bot.query_cache.update({
            100: "bad"
        })
        bot.http_client.expect("post", "/editMessageReplyMarkup",
                               json={'chat_id': -12345678, 'message_id': 12345},
                               content_json={'ok': 1})
        bot.http_client.expect("post", "/answerCallbackQuery",
                               json={'callback_query_id': 123456,
                           'text': "Sorry, button is no longer valid!"},
                               content_json={'ok': 1})
        request = self.request_query("101")
        bot.process_webhook(request)

    def makePollingBot(self, updates, chat_ids=None, authz=None, *args, **kwargs):
        if chat_ids is None:
            chat_ids = []
        http = self.setupFakeHttp()

        return TestPollingBot(updates, '12345:secret', http, chat_ids, authz, *args, **kwargs)

    @defer.inlineCallbacks
    def test_polling(self):
        bot = self.makePollingBot(2)
        bot._polling_continue = True
        bot.http_client.expect("post", "/deleteWebhook", content_json={"ok": 1})
        bot.http_client.expect(
            "post", "/getUpdates",
            json={'timeout': bot.poll_timeout},
            content_json={
                'ok': 1,
                'result': [{
                        "update_id": 10000,
                        "message": {
                            "message_id": 123,
                            "from": self.USER,
                            "chat": self.CHANNEL,
                            "date": 1566688888,
                            "text": "ignore"}}]})
        bot.http_client.expect(
            "post", "/getUpdates",
            json={'timeout': bot.poll_timeout, "offset": 10001},
            content_json={
                'ok': 1,
                'result': [{
                        "update_id": 10001,
                        "message": {
                            "message_id": 124,
                            "from": self.USER,
                            "chat": self.CHANNEL,
                            "date": 1566688889,
                            "text": "/nay"}}]})
        bot.http_client.expect(
            "post", "/sendMessage",
            json={'chat_id': -12345678, 'text': 'Never mind, Harry...', 'parse_mode': 'Markdown'},
            content_json={'ok': 1, 'result': {'message_id': 125}})
        yield bot.do_polling()

    def test_format_build_status(self):
        bot = self.makeBot()
        build = {'results': SUCCESS}
        self.assertEqual(bot.format_build_status(build), "completed successfully ✅")

    def test_format_build_status_short(self):
        bot = self.makeBot()
        build = {'results': WARNINGS}
        self.assertEqual(bot.format_build_status(build, short=True), " ⚠️")

    class HttpServiceWithErrors(fakehttpclientservice.HTTPClientService):

        def __init__(self, skip, errs, *args, **kwargs):
            self.__skip = skip
            self.__errs = errs
            self.succeeded = False
            super().__init__(*args, **kwargs)

        def post(self, ep, **kwargs):
            if self.__skip:
                self.__skip -= 1
            else:
                if self.__errs:
                    self.__errs -= 1
                    raise RuntimeError("{}".format(self.__errs + 1))
                self.succeeded = True
            return super().post(ep, **kwargs)

    def setupFakeHttpWithErrors(self, skip, errs):
        return self.successResultOf(self.HttpServiceWithErrors.getFakeService(
            self.master, self, skip, errs, 'https://api.telegram.org/bot12345:secret'))

    @defer.inlineCallbacks
    def test_post_not_ok(self):
        bot = self.makeBot()
        bot.http_client.expect(
            "post", "/post",
            content_json={'ok': 0})

        def log(msg):
            logs.append(msg)
        logs = []
        bot.log = log

        yield bot.post("/post")
        self.assertIn("ERROR", logs[0])

    def test_post_need_repeat(self):
        bot = self.makeBot()
        bot.http_client = self.setupFakeHttpWithErrors(0, 2)
        bot.http_client.expect(
            "post", "/post",
            content_json={'ok': 1})

        def log(msg):
            logs.append(msg)
        logs = []
        bot.log = log

        bot.post("/post")
        self.assertIn("ERROR", logs[0])

        self.reactor.pump(3 * [30.])

        self.assertTrue(bot.http_client.succeeded)

    def test_polling_need_repeat(self):
        bot = self.makePollingBot(1)
        bot.reactor = self.reactor
        bot.http_client = self.setupFakeHttpWithErrors(1, 2)
        bot._polling_continue = True
        bot.http_client.expect("post", "/deleteWebhook", content_json={"ok": 1})
        bot.http_client.expect(
            "post", "/getUpdates",
            json={'timeout': bot.poll_timeout},
            content_json={
                'ok': 1,
                'result': [{
                        "update_id": 10000,
                        "message": {
                            "message_id": 123,
                            "from": self.USER,
                            "chat": self.CHANNEL,
                            "date": 1566688888,
                            "text": "ignore"}}]})

        def log(msg):
            logs.append(msg)
        logs = []
        bot.log = log

        bot.do_polling()
        self.assertIn("ERROR", logs[0])

        self.reactor.pump(3 * [30.])

        self.assertTrue(bot.http_client.succeeded)
