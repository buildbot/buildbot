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

import hashlib
from typing import TYPE_CHECKING
from unittest import mock

import sqlalchemy as sa
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import base
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import sautils

if TYPE_CHECKING:
    from sqlalchemy.future.engine import Connection


class TestBase(unittest.TestCase):
    def setUp(self):
        meta = sa.MetaData()
        self.tbl = sautils.Table(
            'tbl', meta, sa.Column('str32', sa.String(length=32)), sa.Column('txt', sa.Text)
        )
        self.db = mock.Mock()
        self.db.pool.engine.dialect.name = 'mysql'
        self.comp = base.DBConnectorComponent(self.db)

    def test_checkLength_ok(self):
        self.comp.checkLength(self.tbl.c.str32, "short string")

    def test_checkLength_long(self):
        with self.assertRaises(RuntimeError):
            self.comp.checkLength(self.tbl.c.str32, ("long string" * 5))

    def test_ensureLength_ok(self):
        v = self.comp.ensureLength(self.tbl.c.str32, "short string")
        self.assertEqual(v, "short string")

    def test_ensureLength_long(self):
        v = self.comp.ensureLength(self.tbl.c.str32, "short string" * 5)
        self.assertEqual(v, "short stringshordacf5a81f8ae3873")
        self.comp.checkLength(self.tbl.c.str32, v)

    def test_checkLength_text(self):
        with self.assertRaises(AssertionError):
            self.comp.checkLength(self.tbl.c.txt, ("long string" * 5))

    def test_checkLength_long_not_mysql(self):
        self.db.pool.engine.dialect.name = 'sqlite'
        self.comp.checkLength(self.tbl.c.str32, "long string" * 5)
        # run that again since the method gets stubbed out
        self.comp.checkLength(self.tbl.c.str32, "long string" * 5)


class TestBaseAsConnectorComponent(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_findSomethingId_race(self):
        tbl = self.db.model.masters
        hash = hashlib.sha1(b'somemaster').hexdigest()

        def race_thd(conn: Connection):
            conn.execute(
                tbl.insert().values(
                    id=5, name='somemaster', name_hash=hash, active=1, last_active=1
                )
            )
            conn.commit()

        id = yield self.db.masters.findSomethingId(
            tbl=self.db.model.masters,
            whereclause=(tbl.c.name_hash == hash),
            insert_values={
                "name": "somemaster",
                "name_hash": hash,
                "active": 1,
                "last_active": 1,
            },
            _race_hook=race_thd,
        )
        self.assertEqual(id, 5)

    @defer.inlineCallbacks
    def test_findSomethingId_new(self):
        tbl = self.db.model.masters
        hash = hashlib.sha1(b'somemaster').hexdigest()
        id = yield self.db.masters.findSomethingId(
            tbl=self.db.model.masters,
            whereclause=(tbl.c.name_hash == hash),
            insert_values={"name": 'somemaster', "name_hash": hash, "active": 1, "last_active": 1},
        )
        self.assertEqual(id, 1)

    @defer.inlineCallbacks
    def test_findSomethingId_existing(self):
        tbl = self.db.model.masters
        hash = hashlib.sha1(b'somemaster').hexdigest()

        yield self.db.insert_test_data([
            fakedb.Master(id=7, name='somemaster', name_hash=hash),
        ])

        id = yield self.db.masters.findSomethingId(
            tbl=self.db.model.masters,
            whereclause=(tbl.c.name_hash == hash),
            insert_values={"name": 'somemaster', "name_hash": hash, "active": 1, "last_active": 1},
        )
        self.assertEqual(id, 7)

    @defer.inlineCallbacks
    def test_findSomethingId_new_noCreate(self):
        tbl = self.db.model.masters
        hash = hashlib.sha1(b'somemaster').hexdigest()
        id = yield self.db.masters.findSomethingId(
            tbl=self.db.model.masters,
            whereclause=(tbl.c.name_hash == hash),
            insert_values={"name": 'somemaster', "name_hash": hash, "active": 1, "last_active": 1},
            autoCreate=False,
        )
        self.assertEqual(id, None)


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

        self.assertEqual((res1, res2, comp.invocations), ('foofoo', 'barbar', ['foo', 'bar']))

    @defer.inlineCallbacks
    def test_cached_no_cache(self):
        # attach it to the connector
        connector = mock.Mock(name="connector")
        connector.master.caches.get_cache = self.get_cache
        self.cache_get_raises_exception = True

        # build an instance
        comp = self.TestConnectorComponent(connector)

        yield comp.getThing("foo", no_cache=1)
