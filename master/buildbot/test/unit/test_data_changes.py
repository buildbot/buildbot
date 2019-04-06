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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import changes
from buildbot.data import resultspec
from buildbot.process.users import users
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import epoch2datetime


class ChangeEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = changes.ChangeEndpoint
    resourceTypeClass = changes.Change

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.SourceStamp(id=234),
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                          repository='svn://...', codebase='cbsvn',
                          project='world-domination', sourcestampid=234),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

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

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.SourceStamp(id=133),
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                          repository='svn://...', codebase='cbsvn',
                          project='world-domination', sourcestampid=133),
            fakedb.SourceStamp(id=144),
            fakedb.Change(changeid=14, branch='devel', revision='9284',
                          repository='svn://...', codebase='cbsvn',
                          project='world-domination', sourcestampid=144),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get(self):
        changes = yield self.callGet(('changes',))

        self.validateData(changes[0])
        self.assertEqual(changes[0]['changeid'], 13)
        self.validateData(changes[1])
        self.assertEqual(changes[1]['changeid'], 14)

    @defer.inlineCallbacks
    def test_getRecentChanges(self):
        resultSpec = resultspec.ResultSpec(limit=1, order=('-changeid',))
        changes = yield self.callGet(('changes',), resultSpec=resultSpec)

        self.validateData(changes[0])
        self.assertEqual(changes[0]['changeid'], 14)
        self.assertEqual(len(changes), 1)

    @defer.inlineCallbacks
    def test_getChangesOtherOrder(self):
        resultSpec = resultspec.ResultSpec(limit=1, order=('-when_time_stamp',))
        changes = yield self.callGet(('changes',), resultSpec=resultSpec)

        # limit not implemented for other order
        self.assertEqual(len(changes), 2)

    @defer.inlineCallbacks
    def test_getChangesOtherOffset(self):
        resultSpec = resultspec.ResultSpec(
            limit=1, offset=1, order=('-changeid',))
        changes = yield self.callGet(('changes',), resultSpec=resultSpec)

        # limit not implemented for other offset
        self.assertEqual(len(changes), 2)


class Change(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):
    changeEvent = {
        'author': 'warner',
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

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True,
                                             wantData=True)
        self.rtype = changes.Change(self.master)

    def test_signature_addChange(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.addChange,  # fake
            self.rtype.addChange)  # real
        def addChange(self, files=None, comments=None, author=None,
                      revision=None, when_timestamp=None, branch=None, category=None,
                      revlink='', properties=None, repository='', codebase=None,
                      project='', src=None):
            pass

    @defer.inlineCallbacks
    def do_test_addChange(self, kwargs,
                          expectedRoutingKey, expectedMessage, expectedRow,
                          expectedChangeUsers=None):
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
        self.master.db.changes.assertChange(500, expectedRow)
        self.master.db.changes.assertChangeUsers(500, expectedChangeUsers)

    def test_addChange(self):
        # src and codebase are default here
        kwargs = dict(author='warner', branch='warnerdb',
                      category='devel', comments='fix whitespace',
                      files=['master/buildbot/__init__.py'],
                      project='Buildbot', repository='git://warner',
                      revision='0e92a098b', revlink='http://warner/0e92a098b',
                      when_timestamp=256738404,
                      properties={'foo': 20})
        expectedRoutingKey = ('changes', '500', 'new')
        expectedMessage = self.changeEvent
        expectedRow = fakedb.Change(
            changeid=500,
            author='warner',
            comments='fix whitespace',
            branch='warnerdb',
            revision='0e92a098b',
            revlink='http://warner/0e92a098b',
            when_timestamp=256738404,
            category='devel',
            repository='git://warner',
            codebase='',
            project='Buildbot',
            sourcestampid=100,
        )
        return self.do_test_addChange(kwargs,
                                      expectedRoutingKey, expectedMessage, expectedRow)

    @defer.inlineCallbacks
    def test_addChange_src_codebase(self):
        createUserObject = mock.Mock(spec=users.createUserObject)
        createUserObject.return_value = defer.succeed(123)
        self.patch(users, 'createUserObject', createUserObject)
        kwargs = dict(author='warner', branch='warnerdb',
                      category='devel', comments='fix whitespace',
                      files=['master/buildbot/__init__.py'],
                      project='Buildbot', repository='git://warner',
                      revision='0e92a098b', revlink='http://warner/0e92a098b',
                      when_timestamp=256738404,
                      properties={'foo': 20}, src='git', codebase='cb')
        expectedRoutingKey = ('changes', '500', 'new')
        expectedMessage = {
            'author': 'warner',
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
        expectedRow = fakedb.Change(
            changeid=500,
            author='warner',
            comments='fix whitespace',
            branch='warnerdb',
            revision='0e92a098b',
            revlink='http://warner/0e92a098b',
            when_timestamp=256738404,
            category='devel',
            repository='git://warner',
            codebase='cb',
            project='Buildbot',
            sourcestampid=100,
        )
        yield self.do_test_addChange(kwargs,
                                   expectedRoutingKey, expectedMessage, expectedRow,
                                   expectedChangeUsers=[123])

        createUserObject.assert_called_once_with(self.master, 'warner', 'git')

    def test_addChange_src_codebaseGenerator(self):
        def preChangeGenerator(**kwargs):
            return kwargs
        self.master.config = mock.Mock(name='master.config')
        self.master.config.preChangeGenerator = preChangeGenerator
        self.master.config.codebaseGenerator = \
            lambda change: 'cb-%s' % change['category']
        kwargs = dict(author='warner', branch='warnerdb',
                      category='devel', comments='fix whitespace',
                      files=['master/buildbot/__init__.py'],
                      project='Buildbot', repository='git://warner',
                      revision='0e92a098b', revlink='http://warner/0e92a098b',
                      when_timestamp=256738404,
                      properties={'foo': 20})
        expectedRoutingKey = ('changes', '500', 'new')
        expectedMessage = {
            'author': 'warner',
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
        expectedRow = fakedb.Change(
            changeid=500,
            author='warner',
            comments='fix whitespace',
            branch='warnerdb',
            revision='0e92a098b',
            revlink='http://warner/0e92a098b',
            when_timestamp=256738404,
            category='devel',
            repository='git://warner',
            codebase='cb-devel',
            project='Buildbot',
            sourcestampid=100,
        )
        return self.do_test_addChange(kwargs,
                                      expectedRoutingKey, expectedMessage, expectedRow)

    def test_addChange_repository_revision(self):
        self.master.config = mock.Mock(name='master.config')
        self.master.config.revlink = lambda rev, repo: 'foo%sbar%sbaz' % (repo, rev)
        # revlink is default here
        kwargs = dict(author='warner', branch='warnerdb',
                      category='devel', comments='fix whitespace',
                      files=['master/buildbot/__init__.py'],
                      project='Buildbot', repository='git://warner',
                      codebase='', revision='0e92a098b', when_timestamp=256738404,
                      properties={'foo': 20})
        expectedRoutingKey = ('changes', '500', 'new')
        # When no revlink is passed to addChange, but a repository and revision is
        # passed, the revlink should be constructed by calling the revlink callable
        # in the config. We thus expect a revlink of 'foogit://warnerbar0e92a098bbaz'
        expectedMessage = {
            'author': 'warner',
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
        expectedRow = fakedb.Change(
            changeid=500,
            author='warner',
            comments='fix whitespace',
            branch='warnerdb',
            revision='0e92a098b',
            revlink='foogit://warnerbar0e92a098bbaz',
            when_timestamp=256738404,
            category='devel',
            repository='git://warner',
            codebase='',
            project='Buildbot',
            sourcestampid=100,
        )
        return self.do_test_addChange(kwargs,
                                      expectedRoutingKey, expectedMessage, expectedRow)
