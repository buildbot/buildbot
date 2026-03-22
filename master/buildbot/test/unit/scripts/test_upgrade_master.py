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

import os
import sys
from io import StringIO
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import master as config_master
from buildbot.db import connector
from buildbot.db import masters
from buildbot.db import model
from buildbot.scripts import base
from buildbot.scripts import upgrade_master
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import dirs
from buildbot.test.util import misc
from buildbot.test.util import www

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


def mkconfig(**kwargs: Any) -> dict[str, Any]:
    config: dict[str, Any] = {"quiet": False, "replace": False, "basedir": 'test'}
    config.update(kwargs)
    return config


class TestUpgradeMaster(dirs.DirsMixin, misc.StdoutAssertionsMixin, unittest.TestCase):
    def setUp(self) -> None:
        # createMaster is decorated with @in_reactor, so strip that decoration
        # since the master is already running
        self.patch(upgrade_master, 'upgradeMaster', upgrade_master.upgradeMaster._orig)  # type: ignore[attr-defined]
        self.setUpDirs('test')
        self.setUpStdoutAssertions()

    def patchFunctions(self, basedirOk: bool = True, configOk: bool = True) -> None:
        self.calls: list[str] = []

        def checkBasedir(config: dict[str, Any]) -> bool:
            self.calls.append('checkBasedir')
            return basedirOk

        self.patch(base, 'checkBasedir', checkBasedir)

        def loadConfig(
            config: dict[str, Any], configFileName: str = 'master.cfg'
        ) -> config_master.MasterConfig | bool:
            self.calls.append('loadConfig')
            return config_master.MasterConfig() if configOk else False

        self.patch(base, 'loadConfig', loadConfig)

        def upgradeFiles(config: dict[str, Any]) -> None:
            self.calls.append('upgradeFiles')

        self.patch(upgrade_master, 'upgradeFiles', upgradeFiles)

        def upgradeDatabase(config: dict[str, Any], master_cfg: config_master.MasterConfig) -> None:
            self.assertIsInstance(master_cfg, config_master.MasterConfig)
            self.calls.append('upgradeDatabase')

        self.patch(upgrade_master, 'upgradeDatabase', upgradeDatabase)

    # tests

    @defer.inlineCallbacks
    def test_upgradeMaster_success(self) -> InlineCallbacksType[None]:
        self.patchFunctions()
        rv = yield upgrade_master.upgradeMaster(mkconfig())

        self.assertEqual(rv, 0)
        self.assertInStdout('upgrade complete')

    @defer.inlineCallbacks
    def test_upgradeMaster_quiet(self) -> InlineCallbacksType[None]:
        self.patchFunctions()
        rv = yield upgrade_master.upgradeMaster(mkconfig(quiet=True))

        self.assertEqual(rv, 0)
        self.assertWasQuiet()

    @defer.inlineCallbacks
    def test_upgradeMaster_bad_basedir(self) -> InlineCallbacksType[None]:
        self.patchFunctions(basedirOk=False)
        rv = yield upgrade_master.upgradeMaster(mkconfig())

        self.assertEqual(rv, 1)

    @defer.inlineCallbacks
    def test_upgradeMaster_bad_config(self) -> InlineCallbacksType[None]:
        self.patchFunctions(configOk=False)
        rv = yield upgrade_master.upgradeMaster(mkconfig())

        self.assertEqual(rv, 1)


class TestUpgradeMasterFunctions(
    www.WwwTestMixin,
    dirs.DirsMixin,
    misc.StdoutAssertionsMixin,
    TestReactorMixin,
    unittest.TestCase,
):
    def setUp(self) -> None:
        self.setup_test_reactor()
        self.setUpDirs('test')
        self.basedir = os.path.abspath(os.path.join('test', 'basedir'))
        self.setUpStdoutAssertions()

    def writeFile(self, path: str, contents: str) -> None:
        with open(path, "w", encoding='utf-8') as f:
            f.write(contents)

    def readFile(self, path: str) -> str:
        with open(path, encoding='utf-8') as f:
            return f.read()

    # tests

    def test_installFile(self) -> None:
        self.writeFile('test/srcfile', 'source data')
        upgrade_master.installFile(mkconfig(), 'test/destfile', 'test/srcfile')
        self.assertEqual(self.readFile('test/destfile'), 'source data')
        self.assertInStdout('creating test/destfile')

    def test_installFile_existing_differing(self) -> None:
        self.writeFile('test/srcfile', 'source data')
        self.writeFile('test/destfile', 'dest data')
        upgrade_master.installFile(mkconfig(), 'test/destfile', 'test/srcfile')
        self.assertEqual(self.readFile('test/destfile'), 'dest data')
        self.assertEqual(self.readFile('test/destfile.new'), 'source data')
        self.assertInStdout('writing new contents to')

    def test_installFile_existing_differing_overwrite(self) -> None:
        self.writeFile('test/srcfile', 'source data')
        self.writeFile('test/destfile', 'dest data')
        upgrade_master.installFile(mkconfig(), 'test/destfile', 'test/srcfile', overwrite=True)
        self.assertEqual(self.readFile('test/destfile'), 'source data')
        self.assertFalse(os.path.exists('test/destfile.new'))
        self.assertInStdout('overwriting')

    def test_installFile_existing_same(self) -> None:
        self.writeFile('test/srcfile', 'source data')
        self.writeFile('test/destfile', 'source data')
        upgrade_master.installFile(mkconfig(), 'test/destfile', 'test/srcfile')
        self.assertEqual(self.readFile('test/destfile'), 'source data')
        self.assertFalse(os.path.exists('test/destfile.new'))
        self.assertWasQuiet()

    def test_installFile_quiet(self) -> None:
        self.writeFile('test/srcfile', 'source data')
        upgrade_master.installFile(mkconfig(quiet=True), 'test/destfile', 'test/srcfile')
        self.assertWasQuiet()

    def test_upgradeFiles(self) -> None:
        upgrade_master.upgradeFiles(mkconfig())
        for f in [
            'test/master.cfg.sample',
        ]:
            self.assertTrue(os.path.exists(f), f"{f} not found")
        self.assertInStdout('upgrading basedir')

    def test_upgradeFiles_notice_about_unused_public_html(self) -> None:
        os.mkdir('test/public_html')
        self.writeFile('test/public_html/index.html', 'INDEX')
        upgrade_master.upgradeFiles(mkconfig())
        self.assertInStdout('public_html is not used')

    @defer.inlineCallbacks
    def test_upgradeDatabase(self) -> InlineCallbacksType[None]:
        setup = mock.Mock(side_effect=lambda **kwargs: defer.succeed(None))
        self.patch(connector.DBConnector, 'setup', setup)
        upgrade = mock.Mock(side_effect=lambda **kwargs: defer.succeed(None))
        self.patch(model.Model, 'upgrade', upgrade)
        setAllMastersActiveLongTimeAgo = mock.Mock(side_effect=lambda **kwargs: defer.succeed(None))
        self.patch(
            masters.MastersConnectorComponent,
            'setAllMastersActiveLongTimeAgo',
            setAllMastersActiveLongTimeAgo,
        )
        yield upgrade_master.upgradeDatabase(
            mkconfig(basedir='test', quiet=True), config_master.MasterConfig()
        )
        setup.asset_called_with(check_version=False, verbose=False)
        upgrade.assert_called_with()
        self.assertWasQuiet()

    @defer.inlineCallbacks
    def test_upgradeDatabaseFail(self) -> InlineCallbacksType[None]:
        setup = mock.Mock(side_effect=lambda **kwargs: defer.succeed(None))
        self.patch(connector.DBConnector, 'setup', setup)
        self.patch(sys, 'stderr', StringIO())
        upgrade = mock.Mock(side_effect=lambda **kwargs: defer.fail(Exception("o noz")))
        self.patch(model.Model, 'upgrade', upgrade)
        ret = yield upgrade_master._upgradeMaster(
            mkconfig(basedir='test', quiet=True), config_master.MasterConfig()
        )
        self.assertEqual(ret, 1)
        self.assertIn(
            "problem while upgrading!:\nTraceback (most recent call last):\n",
            sys.stderr.getvalue(),  # type: ignore[union-attr]
        )
        self.assertIn("o noz", sys.stderr.getvalue())  # type: ignore[union-attr]
