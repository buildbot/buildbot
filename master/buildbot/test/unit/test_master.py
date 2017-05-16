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

import datetime
import os
import signal

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.trial import unittest
from zope.interface import implementer

from buildbot import config
from buildbot import master
from buildbot import monkeypatches
from buildbot.changes.changes import Change
from buildbot.db import exceptions
from buildbot.interfaces import IConfigLoader
from buildbot.test.fake import fakedata
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemq
from buildbot.test.fake.botmaster import FakeBotMaster
from buildbot.test.util import dirs
from buildbot.test.util import logging


@implementer(IConfigLoader)
class FailingLoader(object):

    def loadConfig(self):
        config.error('oh noes')


@implementer(IConfigLoader)
class DefaultLoader(object):

    def loadConfig(self):
        return config.MasterConfig()


class OldTriggeringMethods(unittest.TestCase):

    def setUp(self):
        self.patch(master.BuildMaster, 'create_child_services',
                   lambda self: None)
        self.master = master.BuildMaster(basedir=None)

        self.master.data = fakedata.FakeDataConnector(self.master, self)
        self.master.data.setServiceParent(self.master)
        self.db = self.master.db = fakedb.FakeDBConnector(self)
        self.db.setServiceParent(self.master)
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

    def test_addChange_args_when_timestamp(self):
        # when_timestamp should come through as an epoch time.
        return self.do_test_addChange_args(
            kwargs=dict(when_timestamp=datetime.datetime(1998, 4, 11, 11, 24, 35)),
            exp_data_kwargs=dict(when_timestamp=892293875))

    def test_addChange_args_new_and_old(self):
        func = self.do_test_addChange_args
        kwargs = dict(who='author',
                      author='author'),
        exp_data_kwargs = dict(author='author')
        self.assertRaises(TypeError, func, kwargs=kwargs,
                          exp_data_kwargs=exp_data_kwargs)

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


class InitTests(unittest.SynchronousTestCase):

    def test_configfile_configloader_conflict(self):
        """
        If both configfile and config_loader are specified, a configuration
        error is raised.
        """
        self.assertRaises(
            config.ConfigErrors,
            master.BuildMaster,
            ".", "master.cfg", reactor=reactor, config_loader=DefaultLoader())

    def test_configfile_default(self):
        """
        If neither configfile nor config_loader are specified, The default config_loader is a `FileLoader` pointing at `"master.cfg"`.
        """
        m = master.BuildMaster(".", reactor=reactor)
        self.assertEqual(m.config_loader, config.FileLoader(".", "master.cfg"))


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
            # XXX temporary
            self.patch(master, 'Status', lambda master: mock.Mock())

            master.BuildMaster.masterHeartbeatService = mock.Mock()
            self.reactor = self.make_reactor()
            self.master = master.BuildMaster(
                self.basedir, reactor=self.reactor, config_loader=DefaultLoader())
            self.master.sendBuildbotNetUsageData = mock.Mock()
            self.master.botmaster = FakeBotMaster()
            self.db = self.master.db = fakedb.FakeDBConnector(self)
            self.db.setServiceParent(self.master)
            self.mq = self.master.mq = fakemq.FakeMQConnector(self)
            self.mq.setServiceParent(self.master)
            self.data = self.master.data = fakedata.FakeDataConnector(
                self.master, self)
            self.data.setServiceParent(self.master)

        return d

    def tearDown(self):
        return self.tearDownDirs()

    def make_reactor(self):
        r = mock.Mock()
        r.callWhenRunning = reactor.callWhenRunning
        r.getThreadPool = reactor.getThreadPool
        r.callFromThread = reactor.callFromThread
        return r

    # tests
    def test_startup_bad_config(self):
        self.master.config_loader = FailingLoader()

        d = self.master.startService()

        @d.addCallback
        def check(_):
            self.reactor.stop.assert_called_with()
            self.assertLogged("oh noes")
            self.assertLogged("BuildMaster startup failed")
        return d

    def test_startup_db_not_ready(self):
        def db_setup():
            log.msg("GOT HERE")
            raise exceptions.DatabaseNotReadyError()
        self.db.setup = db_setup

        d = self.master.startService()

        @d.addCallback
        def check(_):
            self.reactor.stop.assert_called_with()
            self.assertLogged("GOT HERE")
            self.assertLogged("BuildMaster startup failed")
        return d

    def test_startup_error(self):
        def db_setup():
            raise RuntimeError("oh noes")
        self.db.setup = db_setup

        d = self.master.startService()

        @d.addCallback
        def check(_):
            self.reactor.stop.assert_called_with()
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
            self.assertLogged("BuildMaster startup failed")
        return d

    @defer.inlineCallbacks
    def test_startup_ok(self):
        yield self.master.startService()

        self.assertTrue(self.master.data.updates.thisMasterActive)
        d = self.master.stopService()
        self.assertTrue(d.called)
        self.assertFalse(self.reactor.stop.called)
        self.assertLogged("BuildMaster is running")

        # check started/stopped messages
        self.assertFalse(self.master.data.updates.thisMasterActive)

    @defer.inlineCallbacks
    def test_startup_ok_waitforshutdown(self):
        yield self.master.startService()

        self.assertTrue(self.master.data.updates.thisMasterActive)
        # use fakebotmaster shutdown delaying
        self.master.botmaster.delayShutdown = True
        d = self.master.stopService()

        self.assertFalse(d.called)
        self.master.botmaster.shutdownDeferred.callback(None)
        self.assertTrue(d.called)

        self.assertFalse(self.reactor.stop.called)
        self.assertLogged("BuildMaster is running")

        # check started/stopped messages
        self.assertFalse(self.master.data.updates.thisMasterActive)

    @defer.inlineCallbacks
    def test_reconfig(self):
        self.master.reconfigServiceWithBuildbotConfig = mock.Mock(
            side_effect=lambda n: defer.succeed(None))
        self.master.masterHeartbeatService = mock.Mock()
        yield self.master.startService()
        yield self.master.reconfig()
        yield self.master.stopService()
        self.master.reconfigServiceWithBuildbotConfig.assert_called_with(
            mock.ANY)

    @defer.inlineCallbacks
    def test_reconfig_bad_config(self):
        self.master.reconfigService = mock.Mock(
            side_effect=lambda n: defer.succeed(None))

        self.master.masterHeartbeatService = mock.Mock()
        yield self.master.startService()

        # reset, since startService called reconfigService
        self.master.reconfigService.reset_mock()

        # reconfig, with a failure
        self.master.config_loader = FailingLoader()
        yield self.master.reconfig()

        self.master.stopService()

        self.assertLogged("reconfig aborted without")
        self.assertFalse(self.master.reconfigService.called)

    @defer.inlineCallbacks
    def test_reconfigService_db_url_changed(self):
        old = self.master.config = config.MasterConfig()
        old.db['db_url'] = 'aaaa'
        yield self.master.reconfigServiceWithBuildbotConfig(old)

        new = config.MasterConfig()
        new.db['db_url'] = 'bbbb'

        self.assertRaises(config.ConfigErrors, lambda:
                          self.master.reconfigServiceWithBuildbotConfig(new))
