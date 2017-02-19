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

from __future__ import absolute_import
from __future__ import print_function

import json

import mock

from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.trial import unittest
from twisted.web import client

from buildbot.data import connector as dataconnector
from buildbot.db import connector as dbconnector
from buildbot.mq import connector as mqconnector
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import db
from buildbot.test.util import www
from buildbot.util import bytes2NativeString
from buildbot.util import unicode2bytes
from buildbot.www import service as wwwservice
from buildbot.www import auth
from buildbot.www import authz

SOMETIME = 1348971992
OTHERTIME = 1008971992


class BodyReader(protocol.Protocol):
    # an IProtocol that reads the entire HTTP body and then calls back
    # with it

    def __init__(self, finishedDeferred):
        self.body = []
        self.finishedDeferred = finishedDeferred

    def dataReceived(self, bytes):
        self.body.append(bytes)

    def connectionLost(self, reason):
        if reason.check(client.ResponseDone):
            self.finishedDeferred.callback(b''.join(self.body))
        else:
            self.finishedDeferred.errback(reason)


class Www(db.RealDatabaseMixin, www.RequiresWwwMixin, unittest.TestCase):

    master = None

    @defer.inlineCallbacks
    def setUp(self):
        # set up a full master serving HTTP
        yield self.setUpRealDatabase(table_names=['masters', 'objects', 'object_state'],
                                     sqlite_memory=False)

        master = fakemaster.FakeMaster()

        master.config.db = dict(db_url=self.db_url)
        master.db = dbconnector.DBConnector('basedir')
        master.db.setServiceParent(master)
        yield master.db.setup(check_version=False)

        master.config.mq = dict(type='simple')
        master.mq = mqconnector.MQConnector()
        master.mq.setServiceParent(master)
        master.mq.setup()

        master.data = dataconnector.DataConnector()
        master.data.setServiceParent(master)

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

        # build an HTTP agent, using an explicit connection pool if Twisted
        # supports it (Twisted 13.0.0 and up)
        if hasattr(client, 'HTTPConnectionPool'):
            self.pool = client.HTTPConnectionPool(reactor)
            self.agent = client.Agent(reactor, pool=self.pool)
        else:
            self.pool = None
            self.agent = client.Agent(reactor)

    @defer.inlineCallbacks
    def tearDown(self):
        if self.pool:
            yield self.pool.closeCachedConnections()
        if self.master:
            yield self.master.www.stopService()

    @defer.inlineCallbacks
    def apiGet(self, url, expect200=True):
        pg = yield self.agent.request(b'GET', url)

        # this is kind of obscene, but protocols are like that
        d = defer.Deferred()
        bodyReader = BodyReader(d)
        pg.deliverBody(bodyReader)
        body = yield d

        # check this *after* reading the body, otherwise Trial will
        # complain that the response is half-read
        if expect200 and pg.code != 200:
            self.fail("did not get 200 response for '%s'" % (url,))

        defer.returnValue(json.loads(bytes2NativeString(body)))

    def link(self, suffix):
        return self.url + b'api/v2/' + suffix

    # tests

    # There's no need to be exhaustive here.  The intent is to test that data
    # can get all the way from the DB to a real HTTP client, and a few
    # resources will be sufficient to demonstrate that.

    @defer.inlineCallbacks
    def test_masters(self):
        yield self.insertTestData([
            fakedb.Master(id=7, name='some:master',
                          active=0, last_active=SOMETIME),
            fakedb.Master(id=8, name='other:master',
                          active=1, last_active=OTHERTIME),
        ])

        res = yield self.apiGet(self.link(b'masters'))
        self.assertEqual(res, {
            'masters': [
                {'active': False, 'masterid': 7, 'name': 'some:master',
                 'last_active': SOMETIME},
                {'active': True, 'masterid': 8, 'name': 'other:master',
                 'last_active': OTHERTIME},
            ],
            'meta': {
                'total': 2,
            }})

        res = yield self.apiGet(self.link(b'masters/7'))
        self.assertEqual(res, {
            'masters': [
                {'active': False, 'masterid': 7, 'name': 'some:master',
                 'last_active': SOMETIME},
            ],
            'meta': {
            }})
