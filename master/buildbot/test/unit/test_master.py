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
import os
import signal

from buildbot import config
from buildbot import master
from buildbot import monkeypatches
from buildbot.changes.changes import Change
from buildbot.db import exceptions
from buildbot.test.fake import fakedata
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemq
from buildbot.test.util import dirs
from buildbot.test.util import logging
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.trial import unittest


class OldTriggeringMethods(unittest.TestCase):

    def setUp(self):
        self.patch(master.BuildMaster, 'create_child_services',
                   lambda self: None)
        self.master = master.BuildMaster(basedir=None)

        self.master.data = fakedata.FakeDataConnector(self.master, self)
        self.master.db = fakedb.FakeDBConnector(self.master, self)
        self.master.db.insertTestData([
            fakedb.Change(changeid=1, author='this is a test'),
        ])

        self.fake_Change = mock.Mock(name='fake_Change')

        def fromChdict(master, chdict):
            if chdict['author'] != 'this is a test':
                raise AssertionError("did not get expected chdict")
            return defer.succeed(self.fake_Change)
        self.patch(Change, 'fromChdict', staticmethod(fromChdict))

    def do_test_addChange_args(self, args=(), kwargs={}, exp_data_kwargs={}):
        # add default arguments
        default_data_kwargs = {
            'author': None,
            'branch': None,
            'category': None,
            'codebase': None,
            'comments': None,
            'files': None,
            'project': '',
            'properties': {},
            'repository': '',
            'revision': None,
            'revlink': '',
            'src': None,
            'when_timestamp': None,
        }
        default_data_kwargs.update(exp_data_kwargs)
        exp_data_kwargs = default_data_kwargs

        d = self.master.addChange(*args, **kwargs)

        @d.addCallback
        def check(change):
            self.assertIdentical(change, self.fake_Change)
            self.assertEqual(self.master.data.updates.changesAdded,
                             [exp_data_kwargs])
        return d

    def test_addChange_args_author(self):
        # who should come through as author
        return self.do_test_addChange_args(
            kwargs=dict(who='me'),
            exp_data_kwargs=dict(author='me'))

    def test_addChange_args_when(self):
        # when should come through as when_timestamp, as a datetime
        return self.do_test_addChange_args(
            kwargs=dict(when=892293875),
            exp_data_kwargs=dict(when_timestamp=892293875))

    def test_addChange_args_properties(self):
        # properties should not be qualified with a source
        return self.do_test_addChange_args(
            kwargs=dict(properties={'a': 'b'}),
            exp_data_kwargs=dict(properties={u'a': u'b'}))

    def test_addChange_args_properties_tuple(self):
        # properties should not be qualified with a source
        return self.do_test_addChange_args(
            kwargs=dict(properties={'a': ('b', 'Change')}),
            exp_data_kwargs=dict(properties={'a': ('b', 'Change')}))

    def test_addChange_args_positional(self):
        # master.addChange can take author, files, comments as positional
        # arguments
        return self.do_test_addChange_args(
            args=('me', ['a'], 'com'),
            exp_data_kwargs=dict(author='me', files=['a'], comments='com'))


class StartupAndReconfig(dirs.DirsMixin, logging.LoggingMixin, unittest.TestCase):

    def setUp(self):
        self.setUpLogging()
        self.basedir = os.path.abspath('basedir')
        d = self.setUpDirs(self.basedir)

        @d.addCallback
        def make_master(_):
            # don't create child services
            self.patch(master.BuildMaster, 'create_child_services',
                       lambda self: None)

            # patch out a few other annoying things the master likes to do
            self.patch(monkeypatches, 'patch_all', lambda: None)
            self.patch(signal, 'signal', lambda sig, hdlr: None)
            self.patch(master, 'Status', lambda master: mock.Mock())  # XXX temporary
            self.patch(config.MasterConfig, 'loadConfig',
                       classmethod(lambda cls, b, f: cls()))

            self.master = master.BuildMaster(self.basedir)
            self.db = self.master.db = fakedb.FakeDBConnector(self.master, self)
            self.mq = self.master.mq = fakemq.FakeMQConnector(self.master, self)
            self.data = self.master.data = fakedata.FakeDataConnector(self.master, self)

        return d

    def tearDown(self):
        return self.tearDownDirs()

    def make_reactor(self):
        r = mock.Mock()
        r.callWhenRunning = reactor.callWhenRunning
        return r

    def patch_loadConfig_fail(self):
        @classmethod
        def loadConfig(cls, b, f):
            config.error('oh noes')
        self.patch(config.MasterConfig, 'loadConfig', loadConfig)

    # tests
    def test_startup_bad_config(self):
        reactor = self.make_reactor()
        self.patch_loadConfig_fail()

        d = self.master.startService(_reactor=reactor)

        @d.addCallback
        def check(_):
            reactor.stop.assert_called_with()
            self.assertLogged("oh noes")
        return d

    def test_startup_db_not_ready(self):
        reactor = self.make_reactor()

        def db_setup():
            log.msg("GOT HERE")
            raise exceptions.DatabaseNotReadyError()
        self.db.setup = db_setup

        d = self.master.startService(_reactor=reactor)

        @d.addCallback
        def check(_):
            reactor.stop.assert_called_with()
            self.assertLogged("GOT HERE")
        return d

    def test_startup_error(self):
        reactor = self.make_reactor()

        def db_setup():
            raise RuntimeError("oh noes")
        self.db.setup = db_setup

        d = self.master.startService(_reactor=reactor)

        @d.addCallback
        def check(_):
            reactor.stop.assert_called_with()
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        return d

    def test_startup_ok(self):
        reactor = self.make_reactor()

        d = self.master.startService(_reactor=reactor)

        @d.addCallback
        def check_started(_):
            self.assertTrue(self.master.data.updates.thisMasterActive)
        d.addCallback(lambda _: self.master.stopService())

        @d.addCallback
        def check(_):
            self.failIf(reactor.stop.called)
            self.assertLogged("BuildMaster is running")

            # check started/stopped messages
            self.assertFalse(self.master.data.updates.thisMasterActive)
        return d

    def test_reconfig(self):
        reactor = self.make_reactor()
        self.master.reconfigServiceWithBuildbotConfig = mock.Mock(
            side_effect=lambda n: defer.succeed(None))

        d = self.master.startService(_reactor=reactor)
        d.addCallback(lambda _: self.master.reconfig())
        d.addCallback(lambda _: self.master.stopService())

        @d.addCallback
        def check(_):
            self.master.reconfigServiceWithBuildbotConfig.assert_called_with(mock.ANY)
        return d

    @defer.inlineCallbacks
    def test_reconfig_bad_config(self):
        reactor = self.make_reactor()
        self.master.reconfigService = mock.Mock(
            side_effect=lambda n: defer.succeed(None))

        yield self.master.startService(_reactor=reactor)

        # reset, since startService called reconfigService
        self.master.reconfigService.reset_mock()

        # reconfig, with a failure
        self.patch_loadConfig_fail()
        yield self.master.reconfig()

        self.master.stopService()

        self.assertLogged("reconfig aborted without")
        self.failIf(self.master.reconfigService.called)

    @defer.inlineCallbacks
    def test_reconfigService_db_url_changed(self):
        old = self.master.config = config.MasterConfig()
        old.db['db_url'] = 'aaaa'
        yield self.master.reconfigServiceWithBuildbotConfig(old)

        new = config.MasterConfig()
        new.db['db_url'] = 'bbbb'

        self.assertRaises(config.ConfigErrors, lambda:
                          self.master.reconfigServiceWithBuildbotConfig(new))
