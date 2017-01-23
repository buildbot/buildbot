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

import hashlib

import sqlalchemy as sa

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import base
from buildbot.test.fake import fakedb
from buildbot.test.util import connector_component
from buildbot.util import sautils


class TestBase(unittest.TestCase):

    def setUp(self):
        meta = sa.MetaData()
        self.tbl = sautils.Table('tbl', meta,
                                 sa.Column('str32', sa.String(length=32)),
                                 sa.Column('txt', sa.Text))
        self.db = mock.Mock()
        self.db.pool.engine.dialect.name = 'mysql'
        self.comp = base.DBConnectorComponent(self.db)

    def test_checkLength_ok(self):
        self.comp.checkLength(self.tbl.c.str32, "short string")

    def test_checkLength_long(self):
        self.assertRaises(RuntimeError, lambda:
                          self.comp.checkLength(self.tbl.c.str32, "long string" * 5))

    def test_checkLength_text(self):
        self.assertRaises(AssertionError, lambda:
                          self.comp.checkLength(self.tbl.c.txt, "long string" * 5))

    def test_checkLength_long_not_mysql(self):
        self.db.pool.engine.dialect.name = 'sqlite'
        self.comp.checkLength(self.tbl.c.str32, "long string" * 5)
        # run that again since the method gets stubbed out
        self.comp.checkLength(self.tbl.c.str32, "long string" * 5)

    def _sha1(self, s):
        return hashlib.sha1(s).hexdigest()

    def test_hashColumns_single(self):
        self.assertEqual(self.comp.hashColumns('master'),
                         self._sha1(b'master'))

    def test_hashColumns_multiple(self):
        self.assertEqual(self.comp.hashColumns('a', None, 'b', 1),
                         self._sha1(b'a\0\xf5\x00b\x001'))

    def test_hashColumns_None(self):
        self.assertEqual(self.comp.hashColumns(None),
                         self._sha1(b'\xf5'))

    def test_hashColumns_integer(self):
        self.assertEqual(self.comp.hashColumns(11),
                         self._sha1(b'11'))

    def test_hashColumns_unicode_ascii_match(self):
        self.assertEqual(self.comp.hashColumns('master'),
                         self.comp.hashColumns(u'master'))


class TestBaseAsConnectorComponent(unittest.TestCase,
                                   connector_component.ConnectorComponentMixin):

    def setUp(self):
        # this co-opts the masters table to test findSomethingId
        d = self.setUpConnectorComponent(
            table_names=['masters'])

        @d.addCallback
        def finish_setup(_):
            self.db.base = base.DBConnectorComponent(self.db)
        return d

    @defer.inlineCallbacks
    def test_findSomethingId_race(self):
        tbl = self.db.model.masters
        hash = hashlib.sha1(b'somemaster').hexdigest()

        def race_thd(conn):
            conn.execute(tbl.insert(),
                         id=5, name='somemaster', name_hash=hash,
                         active=1, last_active=1)
        id = yield self.db.base.findSomethingId(
            tbl=self.db.model.masters,
            whereclause=(tbl.c.name_hash == hash),
            insert_values=dict(name='somemaster', name_hash=hash,
                               active=1, last_active=1),
            _race_hook=race_thd)
        self.assertEqual(id, 5)

    @defer.inlineCallbacks
    def test_findSomethingId_new(self):
        tbl = self.db.model.masters
        hash = hashlib.sha1(b'somemaster').hexdigest()
        id = yield self.db.base.findSomethingId(
            tbl=self.db.model.masters,
            whereclause=(tbl.c.name_hash == hash),
            insert_values=dict(name='somemaster', name_hash=hash,
                               active=1, last_active=1))
        self.assertEqual(id, 1)

    @defer.inlineCallbacks
    def test_findSomethingId_existing(self):
        tbl = self.db.model.masters
        hash = hashlib.sha1(b'somemaster').hexdigest()

        yield self.insertTestData([
            fakedb.Master(id=7, name='somemaster', name_hash=hash),
        ])

        id = yield self.db.base.findSomethingId(
            tbl=self.db.model.masters,
            whereclause=(tbl.c.name_hash == hash),
            insert_values=dict(name='somemaster', name_hash=hash,
                               active=1, last_active=1))
        self.assertEqual(id, 7)


class TestCachedDecorator(unittest.TestCase):

    def setUp(self):
        # set this to True to check that cache.get isn't called (for
        # no_cache=1)
        self.cache_get_raises_exception = False

    class TestConnectorComponent(base.DBConnectorComponent):
        invocations = None

        @base.cached("mycache")
        def getThing(self, key):
            if self.invocations is None:
                self.invocations = []
            self.invocations.append(key)
            return defer.succeed(key * 2)

    def get_cache(self, cache_name, miss_fn):
        self.assertEqual(cache_name, "mycache")
        cache = mock.Mock(name="mycache")
        if self.cache_get_raises_exception:
            def ex(key):
                raise RuntimeError("cache.get called unexpectedly")
            cache.get = ex
        else:
            cache.get = miss_fn
        return cache

    # tests

    @defer.inlineCallbacks
    def test_cached(self):
        # attach it to the connector
        connector = mock.Mock(name="connector")
        connector.master.caches.get_cache = self.get_cache

        # build an instance
        comp = self.TestConnectorComponent(connector)

        # test it twice (to test an implementation detail)
        res1 = yield comp.getThing("foo")

        res2 = yield comp.getThing("bar")

        self.assertEqual((res1, res2, comp.invocations),
                         ('foofoo', 'barbar', ['foo', 'bar']))

    @defer.inlineCallbacks
    def test_cached_no_cache(self):
        # attach it to the connector
        connector = mock.Mock(name="connector")
        connector.master.caches.get_cache = self.get_cache
        self.cache_get_raises_exception = True

        # build an instance
        comp = self.TestConnectorComponent(connector)

        yield comp.getThing("foo", no_cache=1)
