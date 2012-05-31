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
import re
import sys
import os
import textwrap
import cStringIO
from twisted.trial import unittest
from buildbot.test.util import dirs, compat
from buildbot.scripts import checkconfig

class TestConfigLoader(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpDirs('configdir')

    def tearDown(self):
        return self.tearDownDirs()

    # tests

    def do_test_load(self, by_name=False, config='', other_files={},
                           stdout_re=None, stderr_re=None):
        configFile = os.path.join('configdir', 'master.cfg')
        with open(configFile, "w") as f:
            f.write(config)
        for filename, contents in other_files.iteritems():
            if type(filename) == type(()):
                fn = os.path.join('configdir', *filename)
                dn = os.path.dirname(fn)
                if not os.path.isdir(dn):
                    os.makedirs(dn)
            else:
                fn = os.path.join('configdir', filename)
            with open(fn, "w") as f:
                f.write(contents)

        if by_name:
            cl = checkconfig.ConfigLoader(configFileName=configFile)
        else:
            cl = checkconfig.ConfigLoader(basedir='configdir')

        old_stdout, old_stderr = sys.stdout, sys.stderr
        stdout = sys.stdout = cStringIO.StringIO()
        stderr = sys.stderr = cStringIO.StringIO()
        try:
            cl.load()
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        if stdout_re:
            stdout = stdout.getvalue()
            self.failUnless(stdout_re.search(stdout), stdout)
        if stderr_re:
            stderr = stderr.getvalue()
            self.failUnless(stderr_re.search(stderr), stderr)

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
                                  slavename='sl'),
                ]
                from buildbot.buildslave import BuildSlave
                c['slaves'] = [
                    BuildSlave('sl', 'pass'),
                ]
                c['slavePortnum'] = 9989
                """)
        self.do_test_load(config=config,
                stdout_re=re.compile('Config file is good!'))

        # (regression) check that sys.path hasn't changed
        self.assertEqual(len(sys.path), len_sys_path)

    @compat.usesFlushLoggedErrors
    def test_failure_ImportError(self):
        config = textwrap.dedent("""\
                import test_scripts_checkconfig_does_not_exist
                """)
        self.do_test_load(config=config,
                stderr_re=re.compile(
                    'No module named test_scripts_checkconfig_does_not_exist'))
        self.flushLoggedErrors()

    @compat.usesFlushLoggedErrors
    def test_failure_no_slaves(self):
        config = textwrap.dedent("""\
                BuildmasterConfig={}
                """)
        self.do_test_load(config=config,
                stderr_re=re.compile('no slaves'))
        self.flushLoggedErrors()

    def test_success_imports(self):
        config = textwrap.dedent("""\
                from othermodule import port
                c = BuildmasterConfig = {}
                c['schedulers'] = []
                c['builders'] = []
                c['slaves'] = []
                c['slavePortnum'] = port
                """)
        other_files = { 'othermodule.py' : 'port = 9989' }
        self.do_test_load(config=config, other_files=other_files)

    def test_success_import_package(self):
        config = textwrap.dedent("""\
                from otherpackage.othermodule import port
                c = BuildmasterConfig = {}
                c['schedulers'] = []
                c['builders'] = []
                c['slaves'] = []
                c['slavePortnum'] = port
                """)
        other_files = {
            ('otherpackage', '__init__.py') : '',
            ('otherpackage', 'othermodule.py') : 'port = 9989',
        }
        self.do_test_load(config=config, other_files=other_files)


class TestCheckconfig(unittest.TestCase):

    def setUp(self):
        self.ConfigLoader = mock.Mock(name='ConfigLoader')
        self.instance = mock.Mock(name='ConfigLoader()')
        self.ConfigLoader.return_value = self.instance
        self.instance.load.return_value = 3
        self.patch(checkconfig, 'ConfigLoader', self.ConfigLoader)

    def test_checkconfig_given_dir(self):
        self.assertEqual(checkconfig.checkconfig(dict(configFile='.')), 3)
        self.ConfigLoader.assert_called_with(basedir='.')
        self.instance.load.assert_called_with(quiet=None)

    def test_checkconfig_given_file(self):
        config = dict(configFile='master.cfg')
        self.assertEqual(checkconfig.checkconfig(config), 3)
        self.ConfigLoader.assert_called_with(configFileName='master.cfg')
        self.instance.load.assert_called_with(quiet=None)

    def test_checkconfig_quiet(self):
        config = dict(configFile='master.cfg', quiet=True)
        self.assertEqual(checkconfig.checkconfig(config), 3)
        self.instance.load.assert_called_with(quiet=True)

