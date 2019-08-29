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
import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest
from twisted.web import client
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

from buildbot.data import connector as dataconnector
from buildbot.db import connector as dbconnector
from buildbot.mq import connector as mqconnector
from buildbot.reporters import telegram
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util import db
from buildbot.test.util import www
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.www import auth
from buildbot.www import authz
from buildbot.www import service as wwwservice


@implementer(IBodyProducer)
class BytesProducer(object):
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class TelegramBot(db.RealDatabaseMixin, www.RequiresWwwMixin, unittest.TestCase):

    master = None

    @defer.inlineCallbacks
    def get_http(self, bot_token):
        base_url = "https://api.telegram.org/bot" + bot_token
        http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, base_url)
        # This is necessary as Telegram will make requests in the reconfig
        http.expect("post", "/setWebhook",
                    params={'url': bytes2unicode(self.bot_url)},
                    content_json={'ok': 1})
        return http

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpRealDatabase(table_names=['objects', 'object_state', 'masters',
                                                  'workers', 'configured_workers', 'connected_workers',
                                                  'builder_masters', 'builders'],
                                     sqlite_memory=False)
        master = fakemaster.FakeMaster(reactor)

        master.data = dataconnector.DataConnector()
        master.data.setServiceParent(master)

        master.config.db = dict(db_url=self.db_url)
        master.db = dbconnector.DBConnector('basedir')
        master.db.setServiceParent(master)
        yield master.db.setup(check_version=False)

        master.config.mq = dict(type='simple')
        master.mq = mqconnector.MQConnector()
        master.mq.setServiceParent(master)
        master.mq.setup()

        master.config.www = dict(
            port='tcp:0:interface=127.0.0.1',
            debug=True,
            auth=auth.NoAuth(),
            authz=authz.Authz(),
            avatar_methods=[],
            logfileName='http.log')
        master.www = wwwservice.WWWService()
        master.www.setServiceParent(master)
        yield master.www.startService()
        yield master.www.reconfigServiceWithBuildbotConfig(master.config)
        session = mock.Mock()
        session.uid = "0"
        master.www.site.sessionFactory = mock.Mock(return_value=session)

        # now that we have a port, construct the real URL and insert it into
        # the config.  The second reconfig isn't really required, but doesn't
        # hurt.
        self.url = 'http://127.0.0.1:%d/' % master.www.getPortnum()
        self.url = unicode2bytes(self.url)
        master.config.buildbotURL = self.url
        yield master.www.reconfigServiceWithBuildbotConfig(master.config)

        self.master = master

        self.agent = client.Agent(reactor)

        # create a telegram bot service
        tb = master.config.services['TelegramBot'] = telegram.TelegramBot(
            bot_token='12345:secret', bot_username="testbot", chat_ids=[-123456],  notify_events=['worker']
        )
        tb._get_http = self.get_http
        tb.setServiceParent(self.master)
        self.bot_url = self.url + b"bot12345:secret"

        yield tb.startService()

        self.sent_messages = []
        def send_message(chat, message, **kwargs):
            self.sent_messages.append((chat, message))
        tb.bot.send_message = send_message

    @defer.inlineCallbacks
    def tearDown(self):
        if self.master:
            yield self.master.config.services['TelegramBot'].stopService()
            yield self.master.www.stopService()

    @defer.inlineCallbacks
    def testWebhook(self):

        payload = unicode2bytes(json.dumps({
            "update_id": 12345,
            "message": {
                "message_id": 123,
                "from": {
                    "id": 123456789,
                    "first_name": "Alice",
                },
                "chat": {
                    "id": -12345678,
                    "title": "Wonderlands",
                    "type": "group"
                },
                "date": 1566688888,
                "text": "/getid",
            }
        }))

        pg = yield self.agent.request(b'POST', self.bot_url,
                                      Headers({'Content-Type': ['application/json']}),
                                      BytesProducer(payload))
        self.assertEqual(pg.code, 202,
                         "did not get 202 response for '{}'".format(bytes2unicode(self.bot_url)))
        self.assertIn('123456789', self.sent_messages[0][1])
        self.assertIn('-12345678', self.sent_messages[1][1])

    @defer.inlineCallbacks
    def testState(self):
        tboid = yield self.master.db.state.getObjectId('testbot', 'buildbot.reporters.telegram.TelegramBotResource')
        yield self.insertTestData([
            fakedb.ObjectState(objectid=tboid, name='notify_contacts',
                               value_json='[[123456789,  ["started", "finished"]]]'),
        ])

        tb = self.master.config.services['TelegramBot']
        yield tb.bot.loadNotifyEvents()
        c = tb.bot.getContact(123456789, 123456789)
        self.assertEquals(c.channel.notify_events, {'started', 'finished'})

    @defer.inlineCallbacks
    def test_missing_worker(self):
        yield self.insertTestData([fakedb.Worker(name='local1'),])

        tb = self.master.config.services['TelegramBot']
        channel = tb.bot.getChannel(-123456)
        self.assertEquals(channel.notify_events, {'worker'})

        yield self.master.data.updates.workerMissing(
            workerid='local1',
            masterid=self.master.masterid,
            last_connection='long time ago',
            notify=['admin@worker.org'],
        )
        self.assertEquals(self.sent_messages[-1][1],
                          "Worker local1 is missing. It was seen last at long time ago.")
