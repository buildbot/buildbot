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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.reporters import telegram
from buildbot.reporters import words
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.fake.web import FakeRequest
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import service
from buildbot.util import unicode2bytes

USER = {
    "id": 123456789,
    "first_name": "Harry",
    "last_name": "Potter",
    "username": "harrypotter",
}

CHAT = {
    "id": -12345678,
    "title": "Hogwards",
    "type": "group"
}


class TestTelegramContact(unittest.TestCase, TestReactorMixin):

    class FakeBot():
        commandPrefix = '/'
        nickname = 'nick'
        commandSuffix = '@' + nickname
        useRevisions = False

        def __init__(self):
            self.sent = []

        def send_message(self, channel, message, **kwargs):
            if isinstance(channel, dict):
                channel = channel['id']
            self.sent.append((channel, message))
            return {'message_id': 123}

        def edit_message(self, chat, msgid, message, **kwargs):
            return {'message_id': 123}

        def delete_message(self, chat, msgid):
            pass

        def send_sticker(self, chat, sticker, **kwargs):
            pass

        def getChannel(self, channel):
            return telegram.TelegramChannel(self, channel)

    def setUp(self):
        self.setUpTestReactor()
        self.bot = self.FakeBot()

    def testDescribeUser(self):
        contact = telegram.TelegramContact(self.bot, USER, USER)
        self.assertEquals(contact.describeUser(), "Harry Potter (@harrypotter)")

    def testDescribeUserInGroup(self):
        contact = telegram.TelegramContact(self.bot, USER, CHAT)
        self.assertEquals(contact.describeUser(), "Harry Potter (@harrypotter) on 'Hogwards'")


    @defer.inlineCallbacks
    def test_command_dance(self):
        self.bot.reactor = self.reactor
        contact = telegram.TelegramContact(self.bot, USER, USER)
        yield contact.command_DANCE('')
        self.assertEqual(self.bot.sent[0][0], USER['id'])

    @defer.inlineCallbacks
    def test_commmand_commands_botfather(self):
        contact = telegram.TelegramContact(self.bot, USER, CHAT)
        yield contact.command_COMMANDS('botfather')
        self.assertEqual(self.bot.sent[0][0], CHAT['id'])
        self.assertRegex(self.bot.sent[0][1], r"^\w+ - \S+")

    @defer.inlineCallbacks
    def test_command_getid(self):
        contact = telegram.TelegramContact(self.bot, USER, CHAT)
        yield contact.command_GETID('')
        self.assertIn(str(USER['id']), self.bot.sent[0][1])
        self.assertIn(str(CHAT['id']), self.bot.sent[1][1])


class TestTelegramService(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    class FakeContact(service.AsyncService):

        def __init__(self, bot, user=None, channel=None):
            super().__init__()
            self.bot = bot
            self.user = user
            self.channel = channel
            self.partial = ''
            self.messages = []

        def handleMessage(self, message, **kwargs):
            self.messages.append(message)
            return defer.succeed(message)

    def setupFakeHttp(self):
        return self.successResultOf(fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://api.telegram.org/bot12345:secret'))

    def makeBot(self, chat_ids=None, authz=None, *args, **kwargs):
        if chat_ids is None:
            chat_ids = []
        http = self.setupFakeHttp()
        return telegram.TelegramBotResource('12345:secret', http, chat_ids, authz, *args, **kwargs)

    def test_getContact(self):
        bot = self.makeBot()
        c1 = bot.getContact(USER, USER)
        c2 = bot.getContact(USER, CHAT)
        c1b = bot.getContact(USER, USER)
        self.assertIs(c1, c1b)
        self.assertIsInstance(c2, words.Contact)

    def test_getContact_update(self):
        try:
            bot = self.makeBot()
            contact = bot.getContact(USER, CHAT)
            updated_user = USER.copy()
            updated_user['username'] = "dirtyharry"
            self.assertEquals(contact.user['username'], "harrypotter")
            bot.getContact(updated_user, CHAT)
            self.assertEquals(contact.user['username'], "dirtyharry")
        finally:
            USER['username'] = "harrypotter"

    @defer.inlineCallbacks
    def test_set_webhook(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/setWebhook",
                               json={'url': 'our.webhook'},
                               content_json={'ok': 1})
        m = yield bot.set_webhook('our.webhook')

    @defer.inlineCallbacks
    def test_set_webhook_cert(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/setWebhook",
                               data={'url': 'our.webhook'},
                               files={'certificate': "this is certificate"},
                               content_json={'ok': 1})
        m = yield bot.set_webhook('our.webhook', "this is certificate")

    @defer.inlineCallbacks
    def test_send_message_number(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/sendMessage",
                               json={'chat_id': 1234, 'text': 'Hello',
                           'parse_mode': 'Markdown'},
                               content_json={'ok': 1, 'result': {'message_id': 9876}})
        m = yield bot.send_message(1234, 'Hello')
        self.assertEqual(m['message_id'], 9876)

    @defer.inlineCallbacks
    def test_send_message_dict(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/sendMessage",
                               json={'chat_id': CHAT['id'], 'text': 'Hello',
                           'parse_mode': 'Markdown'},
                               content_json={'ok': 1, 'result': {'message_id': 9876}})
        m = yield bot.send_message(CHAT, 'Hello')
        self.assertEqual(m['message_id'], 9876)

    @defer.inlineCallbacks
    def test_edit_message(self):
        bot = self.makeBot()
        bot.http_client.expect("post", "/editMessageText",
                               json={'chat_id': 1234, 'message_id': 9876, 'text': 'Hello'},
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
            "from": USER,
            "chat": CHAT,
            "date": 1566688888,
            "text": text,
        })

    def request_query(self, data):
        return self.prepare_request(callback_query={
            "id": 123456,
            "from": USER,
            "data": data,
            "message": {
                "message_id": 12345,
                "from": USER,
                "chat": CHAT,
                "date": 1566688888,
        }})

    def test_get_update(self):
        bot = self.makeBot()
        request = self.request_message("test")
        update = bot.get_update(request)
        self.assertEquals(update['message']['from'], USER)
        self.assertEquals(update['message']['chat'], CHAT)

    def test_render_POST(self):
        # This actually also tests process_incoming
        bot = self.makeBot()
        bot.contactClass = self.FakeContact
        request = self.request_message("test")
        bot.render_POST(request)
        contact = bot.getContact(USER['id'], CHAT['id'])
        self.assertEquals(contact.messages, ["test"])

    def test_parse_query_cached(self):
        bot = self.makeBot()
        bot.contactClass = self.FakeContact
        bot.query_cache.update({
            100: "good"
        })
        bot.http_client.expect("post", "/answerCallbackQuery",
                               json={'callback_query_id': 123456},
                               content_json={'ok': 1})
        request = self.request_query("100")
        bot.process_incoming(request)
        self.assertEquals(bot.getContact(USER['id'], CHAT['id']).messages, ["good"])

    def test_parse_query_explicit(self):
        bot = self.makeBot()
        bot.contactClass = self.FakeContact
        bot.query_cache.update({
            100: "bad"
        })
        bot.http_client.expect("post", "/answerCallbackQuery",
                               json={'callback_query_id': 123456},
                               content_json={'ok': 1})
        request = self.request_query("good")
        bot.process_incoming(request)
        self.assertEquals(bot.getContact(USER['id'], CHAT['id']).messages, ["good"])

    def test_parse_query_bad(self):
        bot = self.makeBot()
        bot.contactClass = self.FakeContact
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
        bot.process_incoming(request)
