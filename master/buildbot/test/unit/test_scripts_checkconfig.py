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

import sys
import os
import textwrap
from twisted.trial import unittest
from buildbot.test.util import dirs
from buildbot.scripts import checkconfig

class TestConfigLoader(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpDirs('configdir')

    def tearDown(self):
        return self.tearDownDirs()

    # tests

    def do_test_load(self, by_name=False, config='', other_files={},
                           exp_failure=False):
        configFile = os.path.join('configdir', 'master.cfg')
        open(configFile, "w").write(config)
        for filename, contents in other_files.iteritems():
            if type(filename) == type(()):
                fn = os.path.join('configdir', *filename)
                dn = os.path.dirname(fn)
                if not os.path.isdir(dn):
                    os.makedirs(dn)
            else:
                fn = os.path.join('configdir', filename)
            open(fn, "w").write(contents)

        if by_name:
            cl = checkconfig.ConfigLoader(configFileName=configFile)
        else:
            cl = checkconfig.ConfigLoader(basedir='configdir')

        d = cl.load()
        if exp_failure:
            def cb(x):
                self.fail("should not get here")
            def eb(f):
                if exp_failure is not True:
                    f.trap(exp_failure)
                return None
            d.addCallbacks(cb, eb)
        return d

    def test_success(self):
        len_sys_path = len(sys.path)
        config = textwrap.dedent("""\
                c = BuildmasterConfig = {}
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
        d = self.do_test_load(config=config)
        def check(_):
            # check that the builder directory was not created
            self.assertFalse(os.path.exists(
                os.path.join('configdir', 'testbuilder')))
            # ..nor the state database
            self.assertFalse(os.path.exists(
                os.path.join('configdir', 'state.sqlite')))
            self.assertEqual(len(sys.path), len_sys_path)
        return d

    def test_failure_ImportError(self):
        config = textwrap.dedent("""\
                import test_scripts_checkconfig_does_not_exist
                """)
        d = self.do_test_load(config=config, exp_failure=ImportError)
        return d

    def test_failure_SyntaxError(self):
        config = textwrap.dedent("""\
                "untermina
                """)
        d = self.do_test_load(config=config, exp_failure=SyntaxError)
        return d

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
        d = self.do_test_load(config=config, other_files=other_files)
        return d

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
        d = self.do_test_load(config=config, other_files=other_files)
        return d

