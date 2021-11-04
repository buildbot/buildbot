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


import textwrap

from twisted.internet import defer
from twisted.python import reflect
from twisted.trial import unittest

from buildbot.data import connector
from buildbot.data.graphql import GraphQLConnector
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import interfaces

try:
    import graphql
except ImportError:
    graphql = None


class TestGraphQlConnector(TestReactorMixin, unittest.TestCase, interfaces.InterfaceTests):
    maxDiff = None

    @defer.inlineCallbacks
    def setUp(self):
        if not graphql:
            raise unittest.SkipTest('Test requires graphql-core module installed')
        self.setup_test_reactor(use_asyncio=True)
        self.master = fakemaster.make_master(self)
        # don't load by default
        self.all_submodules = connector.DataConnector.submodules
        self.patch(connector.DataConnector, 'submodules', [])
        self.master.data = self.data = connector.DataConnector()
        yield self.data.setServiceParent(self.master)
        self.graphql = GraphQLConnector()
        yield self.graphql.setServiceParent(self.master)

    def configure_graphql(self):
        self.master.config.www = {'graphql': {}}
        self.graphql.reconfigServiceWithBuildbotConfig(self.master.config)

    def test_signature_query(self):
        @self.assertArgSpecMatches(self.graphql.query)
        def query(self, query):
            pass

    def test_graphql_get_schema(self):

        # use the test module for basic graphQLSchema generation
        mod = reflect.namedModule('buildbot.test.unit.data.test_connector')
        self.data._scanModule(mod)
        self.configure_graphql()
        schema = self.graphql.get_schema()
        self.assertEqual(schema, textwrap.dedent("""
        # custom scalar types for buildbot data model
        scalar Date   # stored as utc unix timestamp
        scalar Binary # arbitrary data stored as base85
        scalar JSON  # arbitrary json stored as string, mainly used for properties values
        type Query {
          tests(testid: Int,
           testid__contains: Int,
           testid__eq: Int,
           testid__ge: Int,
           testid__gt: Int,
           testid__in: [Int],
           testid__le: Int,
           testid__lt: Int,
           testid__ne: Int,
           testid__notin: [Int],
           order: String,
           limit: Int,
           offset: Int): [Test]!
          test(testid: Int): Test
        }
        type Subscription {
          tests(testid: Int,
           testid__contains: Int,
           testid__eq: Int,
           testid__ge: Int,
           testid__gt: Int,
           testid__in: [Int],
           testid__le: Int,
           testid__lt: Int,
           testid__ne: Int,
           testid__notin: [Int],
           order: String,
           limit: Int,
           offset: Int): [Test]!
          test(testid: Int): Test
        }
        type Test {
          testid: Int!
        }
        """))
        schema = graphql.build_schema(schema)

    def test_get_fake_graphql_schema(self):
        # use the test module for basic graphQLSchema generation
        mod = reflect.namedModule('buildbot.test.fake.endpoint')
        self.data._scanModule(mod)
        self.configure_graphql()
        schema = self.graphql.get_schema()
        self.assertEqual(schema, mod.graphql_schema)
        schema = graphql.build_schema(schema)

    def test_graphql_get_full_schema(self):
        if not graphql:
            raise unittest.SkipTest('Test requires graphql')

        for mod in self.all_submodules:
            mod = reflect.namedModule(mod)
            self.data._scanModule(mod)
        self.configure_graphql()

        schema = self.graphql.get_schema()
        # graphql parses the schema and raise an error if it is incorrect
        # or incoherent (e.g. missing type definition)
        schema = graphql.build_schema(schema)


class TestGraphQlConnectorService(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        if not graphql:
            raise unittest.SkipTest('Test requires graphql-core module installed')
        self.setup_test_reactor(use_asyncio=False)

    @defer.inlineCallbacks
    def test_start_stop(self):
        self.master = fakemaster.make_master(self)
        self.master.data = self.data = connector.DataConnector()
        yield self.data.setServiceParent(self.master)
        self.graphql = GraphQLConnector()
        yield self.graphql.setServiceParent(self.master)
        yield self.master.startService()
        self.master.config.www = {'graphql': {}}
        self.graphql.reconfigServiceWithBuildbotConfig(self.master.config)
        self.assertIsNotNone(self.graphql.asyncio_loop)
        yield self.master.stopService()
        self.assertIsNone(self.graphql.asyncio_loop)
