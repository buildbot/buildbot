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
import zlib
from typing import TYPE_CHECKING
from unittest import mock

from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.trial import unittest
from twisted.web import client
from twisted.web.http_headers import Headers

from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import www
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.util.twisted import async_to_deferred
from buildbot.www import auth
from buildbot.www import authz
from buildbot.www import service as wwwservice

if TYPE_CHECKING:
    from typing import Callable

SOMETIME = 1348971992
OTHERTIME = 1008971992


class BodyReader(protocol.Protocol):
    # an IProtocol that reads the entire HTTP body and then calls back
    # with it

    def __init__(self, finishedDeferred):
        self.body = []
        self.finishedDeferred = finishedDeferred

    def dataReceived(self, data):
        self.body.append(data)

    def connectionLost(self, reason):
        if reason.check(client.ResponseDone):
            self.finishedDeferred.callback(b''.join(self.body))
        else:
            self.finishedDeferred.errback(reason)


class Www(www.RequiresWwwMixin, unittest.TestCase):
    master = None

    @defer.inlineCallbacks
    def setUp(self):
        # set up a full master serving HTTP
        master = yield fakemaster.make_master(
            self,
            wantRealReactor=True,
            wantDb=True,
            wantData=True,
            sqlite_memory=False,
            auto_shutdown=False,
        )

        master.config.www = {
            "port": 'tcp:0:interface=127.0.0.1',
            "debug": True,
            "auth": auth.NoAuth(),
            "authz": authz.Authz(),
            "avatar_methods": [],
            "logfileName": 'http.log',
        }
        master.www = wwwservice.WWWService()
        yield master.www.setServiceParent(master)
        yield master.www.startService()
        yield master.www.reconfigServiceWithBuildbotConfig(master.config)
        session = mock.Mock()
        session.uid = "0"
        master.www.site.sessionFactory = mock.Mock(return_value=session)

        # now that we have a port, construct the real URL and insert it into
        # the config.  The second reconfig isn't really required, but doesn't
        # hurt.
        self.url = f'http://127.0.0.1:{master.www.getPortnum()}/'
        self.url = unicode2bytes(self.url)
        master.config.buildbotURL = self.url
        yield master.www.reconfigServiceWithBuildbotConfig(master.config)

        self.master = master

        self.addCleanup(self.master.test_shutdown)
        self.addCleanup(self.master.www.stopService)

        # build an HTTP agent, using an explicit connection pool if Twisted
        # supports it (Twisted 13.0.0 and up)
        if hasattr(client, 'HTTPConnectionPool'):
            self.pool = client.HTTPConnectionPool(reactor)
            self.agent = client.Agent(reactor, pool=self.pool)
            self.addCleanup(self.pool.closeCachedConnections)
        else:
            self.pool = None
            self.agent = client.Agent(reactor)

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
            self.fail(f"did not get 200 response for '{url}'")

        return json.loads(bytes2unicode(body))

    def link(self, suffix):
        return self.url + b'api/v2/' + suffix

    # tests

    # There's no need to be exhaustive here.  The intent is to test that data
    # can get all the way from the DB to a real HTTP client, and a few
    # resources will be sufficient to demonstrate that.

    @defer.inlineCallbacks
    def test_masters(self):
        yield self.master.db.insert_test_data([
            fakedb.Master(id=7, active=0, last_active=SOMETIME),
            fakedb.Master(id=8, active=1, last_active=OTHERTIME),
        ])

        res = yield self.apiGet(self.link(b'masters'))
        self.assertEqual(
            res,
            {
                'masters': [
                    {
                        'active': False,
                        'masterid': 7,
                        'name': 'master-7',
                        'last_active': SOMETIME,
                    },
                    {
                        'active': True,
                        'masterid': 8,
                        'name': 'master-8',
                        'last_active': OTHERTIME,
                    },
                ],
                'meta': {
                    'total': 2,
                },
            },
        )

        res = yield self.apiGet(self.link(b'masters/7'))
        self.assertEqual(
            res,
            {
                'masters': [
                    {
                        'active': False,
                        'masterid': 7,
                        'name': 'master-7',
                        'last_active': SOMETIME,
                    },
                ],
                'meta': {},
            },
        )

    async def _test_compression(
        self,
        encoding: bytes,
        decompress_fn: Callable[[bytes], bytes],
    ) -> None:
        assert self.master
        await self.master.db.insert_test_data([
            fakedb.Master(id=7, active=0, last_active=SOMETIME),
        ])

        pg = await self.agent.request(
            b'GET',
            self.link(b'masters/7'),
            headers=Headers({b'accept-encoding': [encoding]}),
        )

        # this is kind of obscene, but protocols are like that
        d: defer.Deferred[bytes] = defer.Deferred()
        bodyReader = BodyReader(d)
        pg.deliverBody(bodyReader)
        body = await d

        self.assertEqual(pg.headers.getRawHeaders(b'content-encoding'), [encoding])

        response = json.loads(bytes2unicode(decompress_fn(body)))
        self.assertEqual(
            response,
            {
                'masters': [
                    {
                        'active': False,
                        'masterid': 7,
                        'name': 'master-7',
                        'last_active': SOMETIME,
                    },
                ],
                'meta': {},
            },
        )

    @async_to_deferred
    async def test_gzip_compression(self):
        await self._test_compression(
            b'gzip',
            decompress_fn=lambda body: zlib.decompress(
                body,
                # use largest wbits possible as twisted customize it
                # see: https://docs.python.org/3/library/zlib.html#zlib.decompress
                wbits=47,
            ),
        )

    @async_to_deferred
    async def test_brotli_compression(self):
        try:
            import brotli
        except ImportError as e:
            raise unittest.SkipTest("brotli not installed, skip the test") from e
        await self._test_compression(b'br', decompress_fn=brotli.decompress)

    @async_to_deferred
    async def test_zstandard_compression(self):
        try:
            import zstandard
        except ImportError as e:
            raise unittest.SkipTest("zstandard not installed, skip the test") from e

        def _decompress(data):
            # zstd cannot decompress data compressed with stream api with a non stream api
            decompressor = zstandard.ZstdDecompressor()
            decompressobj = decompressor.decompressobj()
            return decompressobj.decompress(data) + decompressobj.flush()

        await self._test_compression(b'zstd', decompress_fn=_decompress)
