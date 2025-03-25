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


from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import changes
from buildbot.data import resultspec
from buildbot.db.changes import ChangeModel
from buildbot.process.users import users
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util import epoch2datetime


class ChangeEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = changes.ChangeEndpoint
    resourceTypeClass = changes.Change

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(id=234),
            fakedb.Change(
                changeid=13,
                branch='trunk',
                revision='9283',
                repository='svn://...',
                codebase='cbsvn',
                project='world-domination',
                sourcestampid=234,
            ),
        ])

    @defer.inlineCallbacks
    def test_get_existing(self):
        change = yield self.callGet(('changes', '13'))

        self.validateData(change)
        self.assertEqual(change['project'], 'world-domination')

    @defer.inlineCallbacks
    def test_get_missing(self):
        change = yield self.callGet(('changes', '99'))

        self.assertEqual(change, None)


class ChangesEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = changes.ChangesEndpoint
    resourceTypeClass = changes.Change

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Master(id=1),
            fakedb.Worker(id=1, name='wrk'),
            fakedb.SourceStamp(id=133),
            fakedb.Change(
                changeid=13,
                branch='trunk',
                revision='9283',
                repository='svn://...',
                codebase='cbsvn',
                project='world-domination',
                sourcestampid=133,
                when_timestamp=1000000,
            ),
            fakedb.SourceStamp(id=144),
            fakedb.Change(
                changeid=14,
                branch='devel',
                revision='9284',
                repository='svn://...',
                codebase='cbsvn',
                project='world-domination',
                sourcestampid=144,
                when_timestamp=1000001,
            ),
            fakedb.Builder(id=1, name='builder'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=1, builderid=1, buildsetid=8822),
            fakedb.Build(buildrequestid=1, masterid=1, workerid=1, builderid=1, number=1),
        ])

    @defer.inlineCallbacks
    def test_get(self):
        changes = yield self.callGet(('changes',))
        changes = sorted(changes, key=lambda ch: ch['changeid'])

        self.validateData(changes[0])
        self.assertEqual(changes[0]['changeid'], 13)
        self.validateData(changes[1])
        self.assertEqual(changes[1]['changeid'], 14)

    @defer.inlineCallbacks
    def test_getChanges_from_build(self):
        fake_change = yield self.master.db.changes.getChangeFromSSid(144)

        mockGetChangeById = mock.Mock(
            spec=self.master.db.changes.getChangesForBuild, return_value=[fake_change]
        )
        self.patch(self.master.db.changes, 'getChangesForBuild', mockGetChangeById)

        changes = yield self.callGet(('builds', '1', 'changes'))

        self.validateData(changes[0])
        self.assertEqual(changes[0]['changeid'], 14)

    @defer.inlineCallbacks
    def test_getChanges_from_builder(self):
        fake_change = yield self.master.db.changes.getChangeFromSSid(144)
        mockGetChangeById = mock.Mock(
            spec=self.master.db.changes.getChangesForBuild, return_value=[fake_change]
        )
        self.patch(self.master.db.changes, 'getChangesForBuild', mockGetChangeById)

        changes = yield self.callGet(('builders', '1', 'builds', '1', 'changes'))
        self.validateData(changes[0])
        self.assertEqual(changes[0]['changeid'], 14)

    @defer.inlineCallbacks
    def test_getChanges_recent(self):
        resultSpec = resultspec.ResultSpec(limit=1, order=('-changeid',))
        changes = yield self.callGet(('changes',), resultSpec=resultSpec)

        self.validateData(changes[0])
        self.assertEqual(changes[0]['changeid'], 14)
        self.assertEqual(len(changes), 1)

    @defer.inlineCallbacks
    def test_getChangesOtherOrder(self):
        resultSpec = resultspec.ResultSpec(limit=1, order=('-when_timestamp',))
        changes = yield self.callGet(('changes',), resultSpec=resultSpec)

        self.assertEqual(len(changes), 1)

    @defer.inlineCallbacks
    def test_getChangesOtherOffset(self):
        resultSpec = resultspec.ResultSpec(limit=1, offset=1, order=('-changeid',))
        changes = yield self.callGet(('changes',), resultSpec=resultSpec)

        self.assertEqual(len(changes), 1)


class Change(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):
    changeEvent = {
        'author': 'warner',
        'committer': 'david',
        'branch': 'warnerdb',
        'category': 'devel',
        'codebase': '',
        'comments': 'fix whitespace',
        'changeid': 500,
        'files': ['master/buildbot/__init__.py'],
        'parent_changeids': [],
        'project': 'Buildbot',
        'properties': {'foo': (20, 'Change')},
        'repository': 'git://warner',
        'revision': '0e92a098b',
        'revlink': 'http://warner/0e92a098b',
        'when_timestamp': 256738404,
        'sourcestamp': {
            'branch': 'warnerdb',
            'codebase': '',
            'patch': None,
            'project': 'Buildbot',
            'repository': 'git://warner',
            'revision': '0e92a098b',
            'created_at': epoch2datetime(10000000),
            'ssid': 100,
        },
        # uid
    }

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = changes.Change(self.master)

        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(id=99),  # force minimum ID in tests below
        ])

    def test_signature_addChange(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.addChange,  # fake
            self.rtype.addChange,
        )  # real
        def addChange(
            self,
            files=None,
            comments=None,
            author=None,
            committer=None,
            revision=None,
            when_timestamp=None,
            branch=None,
            category=None,
            revlink='',
            properties=None,
            repository='',
            codebase=None,
            project='',
            src=None,
        ):
            pass

    @defer.inlineCallbacks
    def do_test_addChange(
        self, kwargs, expectedRoutingKey, expectedMessage, expectedRow, expectedChangeUsers=None
    ):
        if expectedChangeUsers is None:
            expectedChangeUsers = []
        self.reactor.advance(10000000)
        changeid = yield self.rtype.addChange(**kwargs)

        self.assertEqual(changeid, 500)
        # check the correct message was received
        self.master.mq.assertProductions([
            (expectedRoutingKey, expectedMessage),
        ])
        # and that the correct data was inserted into the db
        change = yield self.master.db.changes.getChange(500)
        self.assertEqual(change, expectedRow)
        change_users = yield self.master.db.changes.getChangeUids(500)
        self.assertEqual(change_users, expectedChangeUsers)

    def test_addChange(self):
        # src and codebase are default here
        kwargs = {
            "_test_changeid": 500,
            "author": 'warner',
            "committer": 'david',
            "branch": 'warnerdb',
            "category": 'devel',
            "comments": 'fix whitespace',
            "files": ['master/buildbot/__init__.py'],
            "project": 'Buildbot',
            "repository": 'git://warner',
            "revision": '0e92a098b',
            "revlink": 'http://warner/0e92a098b',
            "when_timestamp": 256738404,
            "properties": {'foo': 20},
        }
        expectedRoutingKey = ('changes', '500', 'new')
        expectedMessage = self.changeEvent
        expectedRow = ChangeModel(
            changeid=500,
            author='warner',
            committer='david',
            comments='fix whitespace',
            branch='warnerdb',
            revision='0e92a098b',
            revlink='http://warner/0e92a098b',
            when_timestamp=epoch2datetime(256738404),
            category='devel',
            repository='git://warner',
            codebase='',
            project='Buildbot',
            sourcestampid=100,
            files=['master/buildbot/__init__.py'],
            properties={'foo': (20, 'Change')},
        )
        return self.do_test_addChange(kwargs, expectedRoutingKey, expectedMessage, expectedRow)

    @defer.inlineCallbacks
    def test_addChange_src_codebase(self):
        yield self.master.db.insert_test_data([
            fakedb.User(uid=123),
        ])

        createUserObject = mock.Mock(spec=users.createUserObject)
        createUserObject.return_value = defer.succeed(123)
        self.patch(users, 'createUserObject', createUserObject)
        kwargs = {
            "_test_changeid": 500,
            "author": 'warner',
            "committer": 'david',
            "branch": 'warnerdb',
            "category": 'devel',
            "comments": 'fix whitespace',
            "files": ['master/buildbot/__init__.py'],
            "project": 'Buildbot',
            "repository": 'git://warner',
            "revision": '0e92a098b',
            "revlink": 'http://warner/0e92a098b',
            "when_timestamp": 256738404,
            "properties": {'foo': 20},
            "src": 'git',
            "codebase": 'cb',
        }
        expectedRoutingKey = ('changes', '500', 'new')
        expectedMessage = {
            'author': 'warner',
            'committer': 'david',
            'branch': 'warnerdb',
            'category': 'devel',
            'codebase': 'cb',
            'comments': 'fix whitespace',
            'changeid': 500,
            'files': ['master/buildbot/__init__.py'],
            'parent_changeids': [],
            'project': 'Buildbot',
            'properties': {'foo': (20, 'Change')},
            'repository': 'git://warner',
            'revision': '0e92a098b',
            'revlink': 'http://warner/0e92a098b',
            'when_timestamp': 256738404,
            'sourcestamp': {
                'branch': 'warnerdb',
                'codebase': 'cb',
                'patch': None,
                'project': 'Buildbot',
                'repository': 'git://warner',
                'revision': '0e92a098b',
                'created_at': epoch2datetime(10000000),
                'ssid': 100,
            },
            # uid
        }
        expectedRow = ChangeModel(
            changeid=500,
            author='warner',
            committer='david',
            comments='fix whitespace',
            branch='warnerdb',
            revision='0e92a098b',
            revlink='http://warner/0e92a098b',
            when_timestamp=epoch2datetime(256738404),
            category='devel',
            repository='git://warner',
            codebase='cb',
            project='Buildbot',
            sourcestampid=100,
            files=['master/buildbot/__init__.py'],
            properties={'foo': (20, 'Change')},
        )
        yield self.do_test_addChange(
            kwargs, expectedRoutingKey, expectedMessage, expectedRow, expectedChangeUsers=[123]
        )

        createUserObject.assert_called_once_with(self.master, 'warner', 'git')

    def test_addChange_src_codebaseGenerator(self):
        def preChangeGenerator(**kwargs):
            return kwargs

        self.master.config = mock.Mock(name='master.config')
        self.master.config.preChangeGenerator = preChangeGenerator
        self.master.config.codebaseGenerator = lambda change: f"cb-{(change['category'])}"
        kwargs = {
            "_test_changeid": 500,
            "author": 'warner',
            "committer": 'david',
            "branch": 'warnerdb',
            "category": 'devel',
            "comments": 'fix whitespace',
            "files": ['master/buildbot/__init__.py'],
            "project": 'Buildbot',
            "repository": 'git://warner',
            "revision": '0e92a098b',
            "revlink": 'http://warner/0e92a098b',
            "when_timestamp": 256738404,
            "properties": {'foo': 20},
        }
        expectedRoutingKey = ('changes', '500', 'new')
        expectedMessage = {
            'author': 'warner',
            'committer': 'david',
            'branch': 'warnerdb',
            'category': 'devel',
            'codebase': 'cb-devel',
            'comments': 'fix whitespace',
            'changeid': 500,
            'files': ['master/buildbot/__init__.py'],
            'parent_changeids': [],
            'project': 'Buildbot',
            'properties': {'foo': (20, 'Change')},
            'repository': 'git://warner',
            'revision': '0e92a098b',
            'revlink': 'http://warner/0e92a098b',
            'when_timestamp': 256738404,
            'sourcestamp': {
                'branch': 'warnerdb',
                'codebase': 'cb-devel',
                'patch': None,
                'project': 'Buildbot',
                'repository': 'git://warner',
                'revision': '0e92a098b',
                'created_at': epoch2datetime(10000000),
                'ssid': 100,
            },
            # uid
        }
        expectedRow = ChangeModel(
            changeid=500,
            author='warner',
            committer='david',
            comments='fix whitespace',
            branch='warnerdb',
            revision='0e92a098b',
            revlink='http://warner/0e92a098b',
            when_timestamp=epoch2datetime(256738404),
            category='devel',
            repository='git://warner',
            codebase='cb-devel',
            project='Buildbot',
            sourcestampid=100,
            files=['master/buildbot/__init__.py'],
            properties={'foo': (20, 'Change')},
        )
        return self.do_test_addChange(kwargs, expectedRoutingKey, expectedMessage, expectedRow)

    def test_addChange_repository_revision(self):
        self.master.config = mock.Mock(name='master.config')
        self.master.config.revlink = lambda rev, repo: f'foo{repo}bar{rev}baz'
        # revlink is default here
        kwargs = {
            "_test_changeid": 500,
            "author": 'warner',
            "committer": 'david',
            "branch": 'warnerdb',
            "category": 'devel',
            "comments": 'fix whitespace',
            "files": ['master/buildbot/__init__.py'],
            "project": 'Buildbot',
            "repository": 'git://warner',
            "codebase": '',
            "revision": '0e92a098b',
            "when_timestamp": 256738404,
            "properties": {'foo': 20},
        }
        expectedRoutingKey = ('changes', '500', 'new')
        # When no revlink is passed to addChange, but a repository and revision is
        # passed, the revlink should be constructed by calling the revlink callable
        # in the config. We thus expect a revlink of 'foogit://warnerbar0e92a098bbaz'
        expectedMessage = {
            'author': 'warner',
            'committer': 'david',
            'branch': 'warnerdb',
            'category': 'devel',
            'codebase': '',
            'comments': 'fix whitespace',
            'changeid': 500,
            'files': ['master/buildbot/__init__.py'],
            'parent_changeids': [],
            'project': 'Buildbot',
            'properties': {'foo': (20, 'Change')},
            'repository': 'git://warner',
            'revision': '0e92a098b',
            'revlink': 'foogit://warnerbar0e92a098bbaz',
            'when_timestamp': 256738404,
            'sourcestamp': {
                'branch': 'warnerdb',
                'codebase': '',
                'patch': None,
                'project': 'Buildbot',
                'repository': 'git://warner',
                'revision': '0e92a098b',
                'created_at': epoch2datetime(10000000),
                'ssid': 100,
            },
            # uid
        }
        expectedRow = ChangeModel(
            changeid=500,
            author='warner',
            committer='david',
            comments='fix whitespace',
            branch='warnerdb',
            revision='0e92a098b',
            revlink='foogit://warnerbar0e92a098bbaz',
            when_timestamp=epoch2datetime(256738404),
            category='devel',
            repository='git://warner',
            codebase='',
            project='Buildbot',
            sourcestampid=100,
            files=['master/buildbot/__init__.py'],
            properties={'foo': (20, 'Change')},
        )
        return self.do_test_addChange(kwargs, expectedRoutingKey, expectedMessage, expectedRow)
