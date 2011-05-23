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

import mock
from buildbot.db import base
from twisted.trial import unittest
from twisted.internet import defer

class TestCachedDecorator(unittest.TestCase):

    @defer.deferredGenerator
    def test_cached(self):
        class TestConnectorComponent(base.DBConnectorComponent):
            invocations = None
            @base.cached("mycache")
            def getThing(self, key):
                if self.invocations is None:
                    self.invocations = []
                self.invocations.append(key)
                return defer.succeed(key * 2)

        # build a simple passthrough cache
        def get_cache(cache_name, miss_fn):
            self.assertEqual(cache_name, "mycache")
            cache = mock.Mock(name="mycache")
            def get(key):
                return miss_fn(key)
            cache.get = get
            return cache

        # attach it to the connector
        connector = mock.Mock(name="connector")
        connector.master.caches.get_cache = get_cache

        # build an instance
        comp = TestConnectorComponent(connector)

        # test it twice (to test an implementation detail)
        wfd = defer.waitForDeferred(
            comp.getThing("foo"))
        yield wfd
        res1 = wfd.getResult()

        wfd = defer.waitForDeferred(
            comp.getThing("bar"))
        yield wfd
        res2 = wfd.getResult()

        self.assertEqual((res1, res2, comp.invocations),
                    ('foofoo', 'barbar', ['foo', 'bar']))
