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

import os
import signal
from unittest import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.trial import unittest
from zope.interface import implementer

from buildbot import config
from buildbot import master
from buildbot import monkeypatches
from buildbot.config.master import FileLoader
from buildbot.config.master import MasterConfig
from buildbot.db import exceptions
from buildbot.interfaces import IConfigLoader
from buildbot.process.properties import Interpolate
from buildbot.secrets.manager import SecretManager
from buildbot.test import fakedb
from buildbot.test.fake import fakedata
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakemq
from buildbot.test.fake.botmaster import FakeBotMaster
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import dirs
from buildbot.test.util import logging


@implementer(IConfigLoader)
class FailingLoader:
    def loadConfig(self):
        config.error('oh noes')


@implementer(IConfigLoader)
class DefaultLoader:
    def loadConfig(self):
        master_cfg = MasterConfig()
        master_cfg.db.db_url = Interpolate('sqlite:///path-to-%(secret:db_pwd)s-db-file')
        master_cfg.secretsProviders = [FakeSecretStorage(secretdict={'db_pwd': 's3cr3t'})]
        return master_cfg


class InitTests(unittest.SynchronousTestCase):
    def test_configfile_configloader_conflict(self):
        """
        If both configfile and config_loader are specified, a configuration
        error is raised.
        """
        with self.assertRaises(config.ConfigErrors):
            master.BuildMaster(".", "master.cfg", reactor=reactor, config_loader=DefaultLoader())

    def test_configfile_default(self):
        """
        If neither configfile nor config_loader are specified, The default config_loader is a
        `FileLoader` pointing at `"master.cfg"`.
        """
        m = master.BuildMaster(".", reactor=reactor)
        self.assertEqual(m.config_loader, FileLoader(".", "master.cfg"))


class StartupAndReconfig(dirs.DirsMixin, logging.LoggingMixin, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setUpLogging()
        self.basedir = os.path.abspath('basedir')
        yield self.setUpDirs(self.basedir)

        # don't create child services
        self.patch(master.BuildMaster, 'create_child_services', lambda self: None)

        # patch out a few other annoying things the master likes to do
        self.patch(monkeypatches, 'patch_all', lambda: None)
        self.patch(signal, 'signal', lambda sig, hdlr: None)

        master.BuildMaster.masterHeartbeatService = mock.Mock()
        self.master = master.BuildMaster(
            self.basedir, reactor=self.reactor, config_loader=DefaultLoader()
        )
        self.master.sendBuildbotNetUsageData = mock.Mock()
        self.master.botmaster = FakeBotMaster()
        self.master.caches = fakemaster.FakeCaches()
        self.secrets_manager = self.master.secrets_manager = SecretManager()
        yield self.secrets_manager.setServiceParent(self.master)
        self.master.db = fakedb.FakeDBConnector(self.basedir, self, auto_upgrade=True)
        yield self.master.db.set_master(self.master)

        @defer.inlineCallbacks
        def cleanup():
            if self.master.db.pool is not None:
                yield self.master.db.pool.stop()

        self.addCleanup(cleanup)

        self.master.mq = fakemq.FakeMQConnector(self)
        yield self.master.mq.setServiceParent(self.master)
        self.data = self.master.data = fakedata.FakeDataConnector(self.master, self)
        yield self.data.setServiceParent(self.master)

    @defer.inlineCallbacks
    def assert_this_master_active(self, active):
        masters = yield self.master.data.get(('masters', 1))
        self.assertEqual(masters['active'], active)

    # tests
    @defer.inlineCallbacks
    def test_startup_bad_config(self):
        self.master.config_loader = FailingLoader()

        yield self.master.startService()

        self.assertTrue(self.reactor.stop_called)
        self.assertLogged("oh noes")
        self.assertLogged("BuildMaster startup failed")

    @defer.inlineCallbacks
    def test_startup_db_not_ready(self):
        def db_setup():
            log.msg("GOT HERE")
            raise exceptions.DatabaseNotReadyError()

        self.master.db.setup = db_setup

        yield self.master.startService()

        self.assertTrue(self.reactor.stop_called)
        self.assertLogged("GOT HERE")
        self.assertLogged("BuildMaster startup failed")

    @defer.inlineCallbacks
    def test_startup_error(self):
        def db_setup():
            raise RuntimeError("oh noes")

        self.master.db.setup = db_setup

        yield self.master.startService()

        self.assertTrue(self.reactor.stop_called)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        self.assertLogged("BuildMaster startup failed")

    @defer.inlineCallbacks
    def test_startup_ok(self):
        yield self.master.startService()

        self.assertEqual(
            self.master.db.configured_db_config.db_url,
            'sqlite:///path-to-s3cr3t-db-file',
        )

        yield self.assert_this_master_active(True)
        d = self.master.stopService()
        self.assertTrue(d.called)
        self.assertFalse(self.reactor.stop_called)
        self.assertLogged("BuildMaster is running")

        # check started/stopped messages
        yield self.assert_this_master_active(False)

    @defer.inlineCallbacks
    def test_startup_ok_waitforshutdown(self):
        yield self.master.startService()

        yield self.assert_this_master_active(True)
        # use fakebotmaster shutdown delaying
        self.master.botmaster.delayShutdown = True
        d = self.master.stopService()

        self.assertFalse(d.called)

        # master must only send shutdown once builds are completed
        yield self.assert_this_master_active(True)
        self.master.botmaster.shutdownDeferred.callback(None)
        self.assertTrue(d.called)

        self.assertFalse(self.reactor.stop_called)
        self.assertLogged("BuildMaster is running")

        # check started/stopped messages
        yield self.assert_this_master_active(False)

    @defer.inlineCallbacks
    def test_reconfig(self):
        self.master.reconfigServiceWithBuildbotConfig = mock.Mock(
            side_effect=lambda n: defer.succeed(None)
        )
        self.master.masterHeartbeatService = mock.Mock()
        yield self.master.startService()
        yield self.master.reconfig()
        yield self.master.stopService()
        self.master.reconfigServiceWithBuildbotConfig.assert_called_with(mock.ANY)

    @defer.inlineCallbacks
    def test_reconfig_bad_config(self):
        self.master.reconfigService = mock.Mock(side_effect=lambda n: defer.succeed(None))

        self.master.masterHeartbeatService = mock.Mock()
        yield self.master.startService()

        # reset, since startService called reconfigService
        self.master.reconfigService.reset_mock()

        # reconfig, with a failure
        self.master.config_loader = FailingLoader()
        yield self.master.reconfig()

        self.master.stopService()

        self.assertLogged("configuration update aborted without")
        self.assertFalse(self.master.reconfigService.called)

    @defer.inlineCallbacks
    def test_reconfigService_db_url_changed(self):
        old = self.master.config = MasterConfig()
        old.db.db_url = Interpolate('sqlite:///%(secret:db_pwd)s')
        old.secretsProviders = [FakeSecretStorage(secretdict={'db_pwd': 's3cr3t'})]
        yield self.master.secrets_manager.setup()
        yield self.master.db.setup()
        yield self.master.reconfigServiceWithBuildbotConfig(old)
        self.assertEqual(self.master.db.configured_db_config.db_url, 'sqlite:///s3cr3t')

        new = MasterConfig()
        new.db.db_url = old.db.db_url
        new.secretsProviders = [FakeSecretStorage(secretdict={'db_pwd': 'other-s3cr3t'})]

        with self.assertRaises(config.ConfigErrors):
            yield self.master.reconfigServiceWithBuildbotConfig(new)
