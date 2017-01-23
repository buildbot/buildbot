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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import fakemaster
from buildbot.test.util import scheduler
from buildbot.util import codebase
from buildbot.util import state


class FakeObject(codebase.AbsoluteSourceStampsMixin, state.StateMixin):

    name = 'fake-name'

    def __init__(self, master, codebases):
        self.master = master
        self.codebases = codebases


class TestAbsoluteSourceStampsMixin(unittest.TestCase, scheduler.SchedulerMixin):

    codebases = {'a': {'repository': '', 'branch': 'master'},
                 'b': {'repository': '', 'branch': 'master'}}

    def setUp(self):
        self.master = fakemaster.make_master(
            wantDb=True, wantData=True, testcase=self)
        self.db = self.master.db
        self.object = FakeObject(self.master, self.codebases)

    def mkch(self, **kwargs):
        ch = self.makeFakeChange(**kwargs)
        self.master.db.changes.fakeAddChangeInstance(ch)
        return ch

    @defer.inlineCallbacks
    def test_getCodebaseDict(self):
        cbd = yield self.object.getCodebaseDict('a')
        self.assertEqual(cbd, {'repository': '', 'branch': 'master'})

    def test_getCodebaseDict_not_found(self):
        d = self.object.getCodebaseDict('c')
        self.assertFailure(d, KeyError)
        return d

    @defer.inlineCallbacks
    def test_getCodebaseDict_existing(self):
        self.db.state.fakeState('fake-name', 'FakeObject',
                                lastCodebases={'a': {
                                    'repository': 'A',
                                    'revision': '1234:abc',
                                    'branch': 'master',
                                    'lastChange': 10}})
        cbd = yield self.object.getCodebaseDict('a')
        self.assertEqual(cbd, {'repository': 'A', 'revision': '1234:abc',
                               'branch': 'master', 'lastChange': 10})
        cbd = yield self.object.getCodebaseDict('b')
        self.assertEqual(cbd, {'repository': '', 'branch': 'master'})

    @defer.inlineCallbacks
    def test_recordChange(self):
        yield self.object.recordChange(self.mkch(codebase='a', repository='A', revision='1234:abc', branch='master', number=10))
        self.db.state.assertStateByClass('fake-name', 'FakeObject', lastCodebases={
            'a': {'repository': 'A', 'revision': '1234:abc', 'branch': 'master', 'lastChange': 10}})

    @defer.inlineCallbacks
    def test_recordChange_older(self):
        self.db.state.fakeState('fake-name', 'FakeObject',
                                lastCodebases={'a': {
                                    'repository': 'A',
                                    'revision': '2345:bcd',
                                    'branch': 'master',
                                    'lastChange': 20}})
        yield self.object.getCodebaseDict('a')
        yield self.object.recordChange(self.mkch(codebase='a', repository='A', revision='1234:abc', branch='master', number=10))
        self.db.state.assertStateByClass('fake-name', 'FakeObject', lastCodebases={
            'a': {'repository': 'A', 'revision': '2345:bcd', 'branch': 'master', 'lastChange': 20}})

    @defer.inlineCallbacks
    def test_recordChange_newer(self):
        self.db.state.fakeState('fake-name', 'FakeObject',
                                lastCodebases={'a': {
                                    'repository': 'A',
                                    'revision': '1234:abc',
                                    'branch': 'master',
                                    'lastChange': 10}})
        yield self.object.getCodebaseDict('a')
        yield self.object.recordChange(self.mkch(codebase='a', repository='A', revision='2345:bcd', branch='master', number=20))
        self.db.state.assertStateByClass('fake-name', 'FakeObject', lastCodebases={
            'a': {'repository': 'A', 'revision': '2345:bcd', 'branch': 'master', 'lastChange': 20}})
