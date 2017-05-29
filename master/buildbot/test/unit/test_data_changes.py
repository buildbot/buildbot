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

import mock

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot.data import changes
from buildbot.data import resultspec
from buildbot.process.users import users
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util import epoch2datetime


class ChangeEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = changes.ChangeEndpoint
    resourceTypeClass = changes.Change

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.SourceStamp(id=234),
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283',
                          repository=u'svn://...', codebase=u'cbsvn',
                          project=u'world-domination', sourcestampid=234),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(('changes', '13'))

        @d.addCallback
        def check(change):
            self.validateData(change)
            self.assertEqual(change['project'], 'world-domination')
        return d

    def test_get_missing(self):
        d = self.callGet(('changes', '99'))

        @d.addCallback
        def check(change):
            self.assertEqual(change, None)
        return d


class ChangesEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = changes.ChangesEndpoint
    resourceTypeClass = changes.Change

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.SourceStamp(id=133),
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283',
                          repository=u'svn://...', codebase=u'cbsvn',
                          project=u'world-domination', sourcestampid=133),
            fakedb.SourceStamp(id=144),
            fakedb.Change(changeid=14, branch=u'devel', revision=u'9284',
                          repository=u'svn://...', codebase=u'cbsvn',
                          project=u'world-domination', sourcestampid=144),
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


class Change(interfaces.InterfaceTests, unittest.TestCase):
    changeEvent = {
        'author': u'warner',
        'branch': u'warnerdb',
        'category': u'devel',
        'codebase': u'',
        'comments': u'fix whitespace',
        'changeid': 500,
        'files': [u'master/buildbot/__init__.py'],
        'parent_changeids': [],
        'project': u'Buildbot',
        'properties': {u'foo': (20, u'Change')},
        'repository': u'git://warner',
        'revision': u'0e92a098b',
        'revlink': u'http://warner/0e92a098b',
        'when_timestamp': 256738404,
        'sourcestamp': {
            'branch': u'warnerdb',
            'codebase': u'',
            'patch': None,
            'project': u'Buildbot',
            'repository': u'git://warner',
            'revision': u'0e92a098b',
            'created_at': epoch2datetime(10000000),
            'ssid': 100,
        },
        # uid
    }

    def setUp(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                             wantData=True, testcase=self)
        self.rtype = changes.Change(self.master)

    def test_signature_addChange(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.addChange,  # fake
            self.rtype.addChange)  # real
        def addChange(self, files=None, comments=None, author=None,
                      revision=None, when_timestamp=None, branch=None, category=None,
                      revlink=u'', properties=None, repository=u'', codebase=None,
                      project=u'', src=None):
            pass

    def do_test_addChange(self, kwargs,
                          expectedRoutingKey, expectedMessage, expectedRow,
                          expectedChangeUsers=[]):
        clock = task.Clock()
        clock.advance(10000000)
        d = self.rtype.addChange(_reactor=clock, **kwargs)

        def check(changeid):
            self.assertEqual(changeid, 500)
            # check the correct message was received
            self.master.mq.assertProductions([
                (expectedRoutingKey, expectedMessage),
            ])
            # and that the correct data was inserted into the db
            self.master.db.changes.assertChange(500, expectedRow)
            self.master.db.changes.assertChangeUsers(500, expectedChangeUsers)
        d.addCallback(check)
        return d

    def test_addChange(self):
        # src and codebase are default here
        kwargs = dict(author=u'warner', branch=u'warnerdb',
                      category=u'devel', comments=u'fix whitespace',
                      files=[u'master/buildbot/__init__.py'],
                      project=u'Buildbot', repository=u'git://warner',
                      revision=u'0e92a098b', revlink=u'http://warner/0e92a098b',
                      when_timestamp=256738404,
                      properties={u'foo': 20})
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

    def test_addChange_src_codebase(self):
        createUserObject = mock.Mock(spec=users.createUserObject)
        createUserObject.return_value = defer.succeed(123)
        self.patch(users, 'createUserObject', createUserObject)
        kwargs = dict(author=u'warner', branch=u'warnerdb',
                      category=u'devel', comments=u'fix whitespace',
                      files=[u'master/buildbot/__init__.py'],
                      project=u'Buildbot', repository=u'git://warner',
                      revision=u'0e92a098b', revlink=u'http://warner/0e92a098b',
                      when_timestamp=256738404,
                      properties={u'foo': 20}, src=u'git', codebase=u'cb')
        expectedRoutingKey = ('changes', '500', 'new')
        expectedMessage = {
            'author': u'warner',
            'branch': u'warnerdb',
            'category': u'devel',
            'codebase': u'cb',
            'comments': u'fix whitespace',
            'changeid': 500,
            'files': [u'master/buildbot/__init__.py'],
            'parent_changeids': [],
            'project': u'Buildbot',
            'properties': {u'foo': (20, u'Change')},
            'repository': u'git://warner',
            'revision': u'0e92a098b',
            'revlink': u'http://warner/0e92a098b',
            'when_timestamp': 256738404,
            'sourcestamp': {
                'branch': u'warnerdb',
                'codebase': u'cb',
                'patch': None,
                'project': u'Buildbot',
                'repository': u'git://warner',
                'revision': u'0e92a098b',
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
        d = self.do_test_addChange(kwargs,
                                   expectedRoutingKey, expectedMessage, expectedRow,
                                   expectedChangeUsers=[123])

        @d.addCallback
        def check(_):
            createUserObject.assert_called_once_with(
                self.master, 'warner', 'git')
        return d

    def test_addChange_src_codebaseGenerator(self):
        def preChangeGenerator(**kwargs):
            return kwargs
        self.master.config = mock.Mock(name='master.config')
        self.master.config.preChangeGenerator = preChangeGenerator
        self.master.config.codebaseGenerator = \
            lambda change: 'cb-%s' % change['category']
        kwargs = dict(author=u'warner', branch=u'warnerdb',
                      category=u'devel', comments=u'fix whitespace',
                      files=[u'master/buildbot/__init__.py'],
                      project=u'Buildbot', repository=u'git://warner',
                      revision=u'0e92a098b', revlink=u'http://warner/0e92a098b',
                      when_timestamp=256738404,
                      properties={u'foo': 20})
        expectedRoutingKey = ('changes', '500', 'new')
        expectedMessage = {
            'author': u'warner',
            'branch': u'warnerdb',
            'category': u'devel',
            'codebase': u'cb-devel',
            'comments': u'fix whitespace',
            'changeid': 500,
            'files': [u'master/buildbot/__init__.py'],
            'parent_changeids': [],
            'project': u'Buildbot',
            'properties': {u'foo': (20, u'Change')},
            'repository': u'git://warner',
            'revision': u'0e92a098b',
            'revlink': u'http://warner/0e92a098b',
            'when_timestamp': 256738404,
            'sourcestamp': {
                'branch': u'warnerdb',
                'codebase': u'cb-devel',
                'patch': None,
                'project': u'Buildbot',
                'repository': u'git://warner',
                'revision': u'0e92a098b',
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
        kwargs = dict(author=u'warner', branch=u'warnerdb',
                      category=u'devel', comments=u'fix whitespace',
                      files=[u'master/buildbot/__init__.py'],
                      project=u'Buildbot', repository=u'git://warner',
                      codebase=u'', revision=u'0e92a098b', when_timestamp=256738404,
                      properties={u'foo': 20})
        expectedRoutingKey = ('changes', '500', 'new')
        # When no revlink is passed to addChange, but a repository and revision is
        # passed, the revlink should be constructed by calling the revlink callable
        # in the config. We thus expect a revlink of 'foogit://warnerbar0e92a098bbaz'
        expectedMessage = {
            'author': u'warner',
            'branch': u'warnerdb',
            'category': u'devel',
            'codebase': u'',
            'comments': u'fix whitespace',
            'changeid': 500,
            'files': [u'master/buildbot/__init__.py'],
            'parent_changeids': [],
            'project': u'Buildbot',
            'properties': {u'foo': (20, u'Change')},
            'repository': u'git://warner',
            'revision': u'0e92a098b',
            'revlink': u'foogit://warnerbar0e92a098bbaz',
            'when_timestamp': 256738404,
            'sourcestamp': {
                'branch': u'warnerdb',
                'codebase': u'',
                'patch': None,
                'project': u'Buildbot',
                'repository': u'git://warner',
                'revision': u'0e92a098b',
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
