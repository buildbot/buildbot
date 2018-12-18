# coding: utf-8
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


class InitTests(unittest.SynchronousTestCase):

    def test_configfile_configloader_conflict(self):
        """
        If both configfile and config_loader are specified, a configuration
        error is raised.
        """
        with self.assertRaises(config.ConfigErrors):
            master.BuildMaster(".", "master.cfg",
                               reactor=reactor, config_loader=DefaultLoader())

    def test_configfile_default(self):
        """
        If neither configfile nor config_loader are specified, The default config_loader is a `FileLoader` pointing at `"master.cfg"`.
        """
        m = master.BuildMaster(".", reactor=reactor)
        self.assertEqual(m.config_loader, config.FileLoader(".", "master.cfg"))


class StartupAndReconfig(dirs.DirsMixin, logging.LoggingMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpLogging()
        self.basedir = os.path.abspath('basedir')
        yield self.setUpDirs(self.basedir)

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

    def tearDown(self):
        return self.tearDownDirs()

    def make_reactor(self):
        r = mock.Mock()
        r.callWhenRunning = reactor.callWhenRunning
        r.getThreadPool = reactor.getThreadPool
        r.callFromThread = reactor.callFromThread
        return r

    # tests
    @defer.inlineCallbacks
    def test_startup_bad_config(self):
        self.master.config_loader = FailingLoader()

        yield self.master.startService()

        self.reactor.stop.assert_called_with()
        self.assertLogged("oh noes")
        self.assertLogged("BuildMaster startup failed")

    @defer.inlineCallbacks
    def test_startup_db_not_ready(self):
        def db_setup():
            log.msg("GOT HERE")
            raise exceptions.DatabaseNotReadyError()
        self.db.setup = db_setup

        yield self.master.startService()

        self.reactor.stop.assert_called_with()
        self.assertLogged("GOT HERE")
        self.assertLogged("BuildMaster startup failed")

    @defer.inlineCallbacks
    def test_startup_error(self):
        def db_setup():
            raise RuntimeError("oh noes")
        self.db.setup = db_setup

        yield self.master.startService()

        self.reactor.stop.assert_called_with()
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        self.assertLogged("BuildMaster startup failed")

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

        with self.assertRaises(config.ConfigErrors):
            self.master.reconfigServiceWithBuildbotConfig(new)
