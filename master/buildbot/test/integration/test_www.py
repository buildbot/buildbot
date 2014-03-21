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

from buildbot.data import connector as dataconnector
from buildbot.db import connector as dbconnector
from buildbot.mq import connector as mqconnector
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import db
from buildbot.test.util import www
from buildbot.util import json
from buildbot.www import service as wwwservice
from buildbot.www import auth
from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.trial import unittest
from twisted.web import client
import twisted
twisted.internet.base.DelayedCall.debug = True
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
            self.finishedDeferred.callback(''.join(self.body))
        else:
            self.finishedDeferred.errback(reason)


class Www(db.RealDatabaseMixin, www.RequiresWwwMixin, unittest.TestCase):

    master = None

    @defer.inlineCallbacks
    def setUp(self):
        # set up a full master serving HTTP
        yield self.setUpRealDatabase(table_names=['masters'],
                                     sqlite_memory=False)

        master = fakemaster.FakeMaster()

        master.config.db = dict(db_url=self.db_url)
        master.db = dbconnector.DBConnector(master, 'basedir')
        yield master.db.setup(check_version=False)

        master.config.mq = dict(type='simple')
        master.mq = mqconnector.MQConnector(master)
        master.mq.setup()

        master.data = dataconnector.DataConnector(master)

        master.config.www = dict(
            port='tcp:0:interface=127.0.0.1',
            debug=True,
            auth=auth.NoAuth(),
            url="not yet known",
            avatar_methods=[])
        master.www = wwwservice.WWWService(master)
        yield master.www.startService()
        yield master.www.reconfigService(master.config)

        # now that we have a port, construct the real URL and insert it into
        # the config.  The second reconfig isn't really required, but doesn't
        # hurt.
        self.url = 'http://127.0.0.1:%d/' % master.www.getPortnum()
        master.config.www['url'] = self.url
        yield master.www.reconfigService(master.config)

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
        pg = yield self.agent.request('GET', url)

        # this is kind of obscene, but protocols are like that
        d = defer.Deferred()
        bodyReader = BodyReader(d)
        pg.deliverBody(bodyReader)
        body = yield d

        # check this *after* reading the body, otherwise Trial will
        # complain tha the response is half-read
        if expect200 and pg.code != 200:
            self.fail("did not get 200 response for '%s'" % (url,))

        defer.returnValue(json.loads(body))

    def link(self, suffix):
        return self.url + 'api/v2/' + suffix

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

        res = yield self.apiGet(self.link('masters'))
        self.assertEqual(res, {
            'masters': [
                {'active': False, 'masterid': 7, 'name': 'some:master',
                 'last_active': SOMETIME, 'link': self.link('masters/7')},
                {'active': True, 'masterid': 8, 'name': 'other:master',
                 'last_active': OTHERTIME, 'link': self.link('masters/8')},
            ],
            'meta': {
                'total': 2,
                'links': [
                    {'href': self.link('masters'), 'rel': 'self'}
                ],
            }})

        res = yield self.apiGet(self.link('masters/7'))
        self.assertEqual(res, {
            'masters': [
                {'active': False, 'masterid': 7, 'name': 'some:master',
                 'last_active': SOMETIME, 'link': self.link('masters/7')},
            ],
            'meta': {
                'links': [
                    {'href': self.link('masters/7'), 'rel': 'self'}
                ],
            }})
