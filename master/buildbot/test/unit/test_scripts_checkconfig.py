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
from future.utils import iteritems

import os
import re
import sys
import textwrap

import mock

from twisted.python.compat import NativeStringIO
from twisted.trial import unittest

from buildbot.scripts import base
from buildbot.scripts import checkconfig
from buildbot.test.util import dirs


class TestConfigLoader(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        # config dir must be unique so that the python runtime does not optimize its list of module
        self.configdir = self.mktemp()
        return self.setUpDirs(self.configdir)

    def tearDown(self):
        return self.tearDownDirs()

    # tests

    def do_test_load(self, config='', other_files={},
                     stdout_re=None, stderr_re=None):
        configFile = os.path.join(self.configdir, 'master.cfg')
        with open(configFile, "w") as f:
            f.write(config)
        for filename, contents in iteritems(other_files):
            if isinstance(filename, type(())):
                fn = os.path.join(self.configdir, *filename)
                dn = os.path.dirname(fn)
                if not os.path.isdir(dn):
                    os.makedirs(dn)
            else:
                fn = os.path.join(self.configdir, filename)
            with open(fn, "w") as f:
                f.write(contents)

        old_stdout, old_stderr = sys.stdout, sys.stderr
        stdout = sys.stdout = NativeStringIO()
        stderr = sys.stderr = NativeStringIO()
        try:
            checkconfig._loadConfig(
                basedir=self.configdir, configFile="master.cfg", quiet=False)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        if stdout_re:
            stdout = stdout.getvalue()
            self.assertTrue(stdout_re.search(stdout), stdout)
        if stderr_re:
            stderr = stderr.getvalue()
            self.assertTrue(stderr_re.search(stderr), stderr)

    def test_success(self):
        len_sys_path = len(sys.path)
        config = textwrap.dedent("""\
                c = BuildmasterConfig = {}
                c['multiMaster'] = True
                c['schedulers'] = []
                from buildbot.config import BuilderConfig
                from buildbot.process.factory import BuildFactory
                c['builders'] = [
                    BuilderConfig('testbuilder', factory=BuildFactory(),
                                  workername='worker'),
                ]
                from buildbot.worker import Worker
                c['workers'] = [
                    Worker('worker', 'pass'),
                ]
                c['protocols'] = {'pb': {'port': 9989}}
                """)
        self.do_test_load(config=config,
                          stdout_re=re.compile('Config file is good!'))

        # (regression) check that sys.path hasn't changed
        self.assertEqual(len(sys.path), len_sys_path)

    def test_failure_ImportError(self):
        config = textwrap.dedent("""\
                import test_scripts_checkconfig_does_not_exist
                """)
        # Python 3 displays this error:
        #   No module named 'test_scripts_checkconfig_does_not_exist'
        #
        # Python 2 displays this error:
        #   No module named test_scripts_checkconfig_does_not_exist
        #
        # We need a regexp that matches both.
        self.do_test_load(config=config,
                          stderr_re=re.compile(
                              "No module named '?test_scripts_checkconfig_does_not_exist'?"))
        self.flushLoggedErrors()

    def test_failure_no_workers(self):
        config = textwrap.dedent("""\
                BuildmasterConfig={}
                """)
        self.do_test_load(config=config,
                          stderr_re=re.compile('no workers'))
        self.flushLoggedErrors()

    def test_success_imports(self):
        config = textwrap.dedent("""\
                from othermodule import port
                c = BuildmasterConfig = {}
                c['schedulers'] = []
                c['builders'] = []
                c['workers'] = []
                c['protocols'] = {'pb': {'port': port}}
                """)
        other_files = {'othermodule.py': 'port = 9989'}
        self.do_test_load(config=config, other_files=other_files)

    def test_success_import_package(self):
        config = textwrap.dedent("""\
                from otherpackage.othermodule import port
                c = BuildmasterConfig = {}
                c['schedulers'] = []
                c['builders'] = []
                c['workers'] = []
                c['protocols'] = {'pb': {'port': 9989}}
                """)
        other_files = {
            ('otherpackage', '__init__.py'): '',
            ('otherpackage', 'othermodule.py'): 'port = 9989',
        }
        self.do_test_load(config=config, other_files=other_files)


class TestCheckconfig(unittest.TestCase):

    def setUp(self):
        self.loadConfig = mock.Mock(
            spec=checkconfig._loadConfig, return_value=3)
        # checkconfig is decorated with @in_reactor, so strip that decoration
        # since the reactor is already running
        self.patch(checkconfig, 'checkconfig', checkconfig.checkconfig._orig)
        self.patch(checkconfig, '_loadConfig', self.loadConfig)

    def test_checkconfig_default(self):
        self.assertEqual(checkconfig.checkconfig(dict()), 3)
        self.loadConfig.assert_called_with(basedir=os.getcwd(),
                                           configFile='master.cfg', quiet=None)

    def test_checkconfig_given_dir(self):
        self.assertEqual(checkconfig.checkconfig(dict(configFile='.')), 3)
        self.loadConfig.assert_called_with(basedir='.', configFile='master.cfg',
                                           quiet=None)

    def test_checkconfig_given_file(self):
        config = dict(configFile='master.cfg')
        self.assertEqual(checkconfig.checkconfig(config), 3)
        self.loadConfig.assert_called_with(basedir=os.getcwd(),
                                           configFile='master.cfg', quiet=None)

    def test_checkconfig_quiet(self):
        config = dict(configFile='master.cfg', quiet=True)
        self.assertEqual(checkconfig.checkconfig(config), 3)
        self.loadConfig.assert_called_with(basedir=os.getcwd(),
                                           configFile='master.cfg', quiet=True)

    def test_checkconfig_syntaxError_quiet(self):
        """
        When C{base.getConfigFileFromTac} raises L{SyntaxError},
        C{checkconfig.checkconfig} return an error.
        """
        mockGetConfig = mock.Mock(spec=base.getConfigFileFromTac,
                                  side_effect=SyntaxError)
        self.patch(checkconfig, 'getConfigFileFromTac', mockGetConfig)
        config = dict(configFile='.', quiet=True)
        self.assertEqual(checkconfig.checkconfig(config), 1)
