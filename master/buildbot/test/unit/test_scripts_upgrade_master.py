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

from __future__ import with_statement

import mock
import os

from buildbot import config as config_module
from buildbot.db import connector
from buildbot.db import model
from buildbot.scripts import upgrade_master
from buildbot.test.util import compat
from buildbot.test.util import dirs
from buildbot.test.util import misc
from twisted.internet import defer
from twisted.trial import unittest


def mkconfig(**kwargs):
    config = dict(quiet=False, replace=False, basedir='test')
    config.update(kwargs)
    return config


class TestUpgradeMaster(dirs.DirsMixin, misc.StdoutAssertionsMixin,
                        unittest.TestCase):

    def setUp(self):
        # createMaster is decorated with @in_reactor, so strip that decoration
        # since the master is already running
        self.patch(upgrade_master, 'upgradeMaster',
                   upgrade_master.upgradeMaster._orig)
        self.setUpDirs('test')
        self.setUpStdoutAssertions()

    def patchFunctions(self, basedirOk=True, configOk=True):
        self.calls = []

        def checkBasedir(config):
            self.calls.append('checkBasedir')
            return basedirOk
        self.patch(upgrade_master, 'checkBasedir', checkBasedir)

        def loadConfig(config, configFileName='master.cfg'):
            self.calls.append('loadConfig')
            return config_module.MasterConfig() if configOk else False
        self.patch(upgrade_master, 'loadConfig', loadConfig)

        def upgradeFiles(config):
            self.calls.append('upgradeFiles')
        self.patch(upgrade_master, 'upgradeFiles', upgradeFiles)

        def upgradeDatabase(config, master_cfg):
            self.assertIsInstance(master_cfg, config_module.MasterConfig)
            self.calls.append('upgradeDatabase')
        self.patch(upgrade_master, 'upgradeDatabase', upgradeDatabase)

    # tests

    def test_upgradeMaster_success(self):
        self.patchFunctions()
        d = upgrade_master.upgradeMaster(mkconfig(), _noMonkey=True)

        @d.addCallback
        def check(rv):
            self.assertEqual(rv, 0)
            self.assertInStdout('upgrade complete')
        return d

    def test_upgradeMaster_quiet(self):
        self.patchFunctions()
        d = upgrade_master.upgradeMaster(mkconfig(quiet=True), _noMonkey=True)

        @d.addCallback
        def check(rv):
            self.assertEqual(rv, 0)
            self.assertWasQuiet()
        return d

    def test_upgradeMaster_bad_basedir(self):
        self.patchFunctions(basedirOk=False)
        d = upgrade_master.upgradeMaster(mkconfig(), _noMonkey=True)

        @d.addCallback
        def check(rv):
            self.assertEqual(rv, 1)
        return d

    def test_upgradeMaster_bad_config(self):
        self.patchFunctions(configOk=False)
        d = upgrade_master.upgradeMaster(mkconfig(), _noMonkey=True)

        @d.addCallback
        def check(rv):
            self.assertEqual(rv, 1)
        return d


class TestUpgradeMasterFunctions(dirs.DirsMixin, misc.StdoutAssertionsMixin,
                                 unittest.TestCase):

    def setUp(self):
        self.setUpDirs('test')
        self.basedir = os.path.abspath(os.path.join('test', 'basedir'))
        self.setUpStdoutAssertions()

    def tearDown(self):
        self.tearDownDirs()

    def activeBasedir(self, extra_lines=()):
        with open(os.path.join('test', 'buildbot.tac'), 'wt') as f:
            f.write("from twisted.application import service\n")
            f.write("service.Application('buildmaster')\n")
            f.write("\n".join(extra_lines))

    def writeFile(self, path, contents):
        with open(path, 'wt') as f:
            f.write(contents)

    def readFile(self, path):
        with open(path, 'rt') as f:
            return f.read()

    # tests

    def test_checkBasedir(self):
        self.activeBasedir()
        rv = upgrade_master.checkBasedir(mkconfig())
        self.assertTrue(rv)
        self.assertInStdout('checking basedir')

    def test_checkBasedir_quiet(self):
        self.activeBasedir()
        rv = upgrade_master.checkBasedir(mkconfig(quiet=True))
        self.assertTrue(rv)
        self.assertWasQuiet()

    def test_checkBasedir_no_dir(self):
        rv = upgrade_master.checkBasedir(mkconfig(basedir='doesntexist'))
        self.assertFalse(rv)
        self.assertInStdout('invalid buildmaster directory')

    @compat.skipUnlessPlatformIs('posix')
    def test_checkBasedir_active_pidfile(self):
        self.activeBasedir()
        open(os.path.join('test', 'twistd.pid'), 'w').close()
        rv = upgrade_master.checkBasedir(mkconfig())
        self.assertFalse(rv)
        self.assertInStdout('still running')

    def test_checkBasedir_invalid_rotateLength(self):
        self.activeBasedir(extra_lines=['rotateLength="32"'])
        rv = upgrade_master.checkBasedir(mkconfig())
        self.assertFalse(rv)
        self.assertInStdout('ERROR')
        self.assertInStdout('rotateLength')

    def test_checkBasedir_invalid_maxRotatedFiles(self):
        self.activeBasedir(extra_lines=['maxRotatedFiles="64"'])
        rv = upgrade_master.checkBasedir(mkconfig())
        self.assertFalse(rv)
        self.assertInStdout('ERROR')
        self.assertInStdout('maxRotatedFiles')

    def test_loadConfig(self):
        @classmethod
        def loadConfig(cls, basedir, filename):
            return config_module.MasterConfig()
        self.patch(config_module.MasterConfig, 'loadConfig', loadConfig)
        cfg = upgrade_master.loadConfig(mkconfig())
        self.assertIsInstance(cfg, config_module.MasterConfig)
        self.assertInStdout('checking')

    def test_loadConfig_ConfigErrors(self):
        @classmethod
        def loadConfig(cls, basedir, filename):
            raise config_module.ConfigErrors(['oh noes'])
        self.patch(config_module.MasterConfig, 'loadConfig', loadConfig)
        cfg = upgrade_master.loadConfig(mkconfig())
        self.assertIdentical(cfg, None)
        self.assertInStdout('oh noes')

    def test_loadConfig_exception(self):
        @classmethod
        def loadConfig(cls, basedir, filename):
            raise RuntimeError()
        self.patch(config_module.MasterConfig, 'loadConfig', loadConfig)
        cfg = upgrade_master.loadConfig(mkconfig())
        self.assertIdentical(cfg, None)
        self.assertInStdout('RuntimeError')

    def test_installFile(self):
        self.writeFile('test/srcfile', 'source data')
        upgrade_master.installFile(mkconfig(), 'test/destfile', 'test/srcfile')
        self.assertEqual(self.readFile('test/destfile'), 'source data')
        self.assertInStdout('creating test/destfile')

    def test_installFile_existing_differing(self):
        self.writeFile('test/srcfile', 'source data')
        self.writeFile('test/destfile', 'dest data')
        upgrade_master.installFile(mkconfig(), 'test/destfile', 'test/srcfile')
        self.assertEqual(self.readFile('test/destfile'), 'dest data')
        self.assertEqual(self.readFile('test/destfile.new'), 'source data')
        self.assertInStdout('writing new contents to')

    def test_installFile_existing_differing_overwrite(self):
        self.writeFile('test/srcfile', 'source data')
        self.writeFile('test/destfile', 'dest data')
        upgrade_master.installFile(mkconfig(), 'test/destfile', 'test/srcfile',
                                   overwrite=True)
        self.assertEqual(self.readFile('test/destfile'), 'source data')
        self.assertFalse(os.path.exists('test/destfile.new'))
        self.assertInStdout('overwriting')

    def test_installFile_existing_same(self):
        self.writeFile('test/srcfile', 'source data')
        self.writeFile('test/destfile', 'source data')
        upgrade_master.installFile(mkconfig(), 'test/destfile', 'test/srcfile')
        self.assertEqual(self.readFile('test/destfile'), 'source data')
        self.assertFalse(os.path.exists('test/destfile.new'))
        self.assertWasQuiet()

    def test_installFile_quiet(self):
        self.writeFile('test/srcfile', 'source data')
        upgrade_master.installFile(mkconfig(quiet=True), 'test/destfile',
                                   'test/srcfile')
        self.assertWasQuiet()

    def test_upgradeFiles(self):
        upgrade_master.upgradeFiles(mkconfig())
        for f in [
                'test/public_html',
                'test/public_html/bg_gradient.jpg',
                'test/public_html/default.css',
                'test/public_html/robots.txt',
                'test/public_html/favicon.ico',
                'test/templates',
                'test/master.cfg.sample',
        ]:
            self.assertTrue(os.path.exists(f), "%s not found" % f)
        self.assertInStdout('upgrading basedir')

    def test_upgradeFiles_rename_index_html(self):
        os.mkdir('test/public_html')
        self.writeFile('test/public_html/index.html', 'INDEX')
        upgrade_master.upgradeFiles(mkconfig())
        self.assertFalse(os.path.exists("test/public_html/index.html"))
        self.assertEqual(self.readFile("test/templates/root.html"), 'INDEX')
        self.assertInStdout('Moving ')

    def test_upgradeFiles_index_html_collision(self):
        os.mkdir('test/public_html')
        self.writeFile('test/public_html/index.html', 'INDEX')
        os.mkdir('test/templates')
        self.writeFile('test/templates/root.html', 'ROOT')
        upgrade_master.upgradeFiles(mkconfig())
        self.assertTrue(os.path.exists("test/public_html/index.html"))
        self.assertEqual(self.readFile("test/templates/root.html"), 'ROOT')
        self.assertInStdout('Decide')

    @defer.inlineCallbacks
    def test_upgradeDatabase(self):
        setup = mock.Mock(side_effect=lambda **kwargs: defer.succeed(None))
        self.patch(connector.DBConnector, 'setup', setup)
        upgrade = mock.Mock(side_effect=lambda **kwargs: defer.succeed(None))
        self.patch(model.Model, 'upgrade', upgrade)
        yield upgrade_master.upgradeDatabase(
            mkconfig(basedir='test', quiet=True),
            config_module.MasterConfig())
        setup.asset_called_with(check_version=False, verbose=False)
        upgrade.assert_called_with()
        self.assertWasQuiet()
