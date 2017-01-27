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
from future.utils import itervalues

import os

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import connector
from buildbot.db import model
from buildbot.scripts import create_master
from buildbot.test.util import dirs
from buildbot.test.util import misc
from buildbot.test.util import www


def mkconfig(**kwargs):
    config = dict(force=False, relocatable=False, config='master.cfg',
                  db='sqlite:///state.sqlite', basedir=os.path.abspath('basedir'),
                  quiet=False, **{'no-logrotate': False, 'log-size': 10000000,
                                  'log-count': 10})
    config.update(kwargs)
    return config


class TestCreateMaster(misc.StdoutAssertionsMixin, unittest.TestCase):

    def setUp(self):
        # createMaster is decorated with @in_reactor, so strip that decoration
        # since the master is already running
        self.patch(create_master, 'createMaster',
                   create_master.createMaster._orig)
        self.setUpStdoutAssertions()

    # tests

    def do_test_createMaster(self, config):
        # mock out everything that createMaster calls, then check that
        # they are called, in order
        functions = ['makeBasedir', 'makeTAC', 'makeSampleConfig',
                     'createDB']
        repls = {}
        calls = []
        for fn in functions:
            repl = repls[fn] = mock.Mock(name=fn)
            repl.side_effect = lambda config, fn=fn: calls.append(fn)
            self.patch(create_master, fn, repl)
        repls['createDB'].side_effect = (lambda config:
                                         calls.append(fn) or defer.succeed(None))
        d = create_master.createMaster(config)

        @d.addCallback
        def check(rc):
            self.assertEqual(rc, 0)
            self.assertEqual(calls, functions)
            for repl in itervalues(repls):
                repl.assert_called_with(config)
        return d

    def test_createMaster_quiet(self):
        d = self.do_test_createMaster(mkconfig(quiet=True))

        @d.addCallback
        def check(_):
            self.assertWasQuiet()
        return d

    def test_createMaster_loud(self):
        d = self.do_test_createMaster(mkconfig(quiet=False))

        @d.addCallback
        def check(_):
            self.assertInStdout('buildmaster configured in')
        return d


class TestCreateMasterFunctions(www.WwwTestMixin, dirs.DirsMixin,
                                misc.StdoutAssertionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpDirs('test')
        self.basedir = os.path.abspath(os.path.join('test', 'basedir'))
        self.setUpStdoutAssertions()

    def tearDown(self):
        self.tearDownDirs()

    def assertInTacFile(self, str):
        with open(os.path.join('test', 'buildbot.tac'), 'rt') as f:
            content = f.read()
        self.assertIn(str, content)

    def assertNotInTacFile(self, str):
        with open(os.path.join('test', 'buildbot.tac'), 'rt') as f:
            content = f.read()
        self.assertNotIn(str, content)

    def assertDBSetup(self, basedir=None, db_url='sqlite:///state.sqlite',
                      verbose=True):
        # mock out the database setup
        self.db = mock.Mock()
        self.db.setup.side_effect = lambda *a, **k: defer.succeed(None)
        self.DBConnector = mock.Mock()
        self.DBConnector.return_value = self.db
        self.patch(connector, 'DBConnector', self.DBConnector)

        basedir = basedir or self.basedir
        # pylint: disable=unsubscriptable-object
        self.assertEqual(
            dict(basedir=self.DBConnector.call_args[0][1],
                 db_url=self.DBConnector.call_args[0][0].mkconfig.db['db_url'],
                 verbose=self.db.setup.call_args[1]['verbose'],
                 check_version=self.db.setup.call_args[1]['check_version'],
                 ),
            dict(basedir=self.basedir,
                 db_url=db_url,
                 verbose=True,
                 check_version=False))

    # tests

    def test_makeBasedir(self):
        self.assertFalse(os.path.exists(self.basedir))
        create_master.makeBasedir(mkconfig(basedir=self.basedir))
        self.assertTrue(os.path.exists(self.basedir))
        self.assertInStdout('mkdir %s' % (self.basedir,))

    def test_makeBasedir_quiet(self):
        self.assertFalse(os.path.exists(self.basedir))
        create_master.makeBasedir(mkconfig(basedir=self.basedir, quiet=True))
        self.assertTrue(os.path.exists(self.basedir))
        self.assertWasQuiet()

    def test_makeBasedir_existing(self):
        os.mkdir(self.basedir)
        create_master.makeBasedir(mkconfig(basedir=self.basedir))
        self.assertInStdout('updating existing installation')

    def test_makeTAC(self):
        create_master.makeTAC(mkconfig(basedir='test'))
        self.assertInTacFile("Application('buildmaster')")
        self.assertWasQuiet()

    def test_makeTAC_relocatable(self):
        create_master.makeTAC(mkconfig(basedir='test', relocatable=True))
        self.assertInTacFile("basedir = '.'")  # repr() prefers ''
        self.assertWasQuiet()

    def test_makeTAC_no_logrotate(self):
        create_master.makeTAC(
            mkconfig(basedir='test', **{'no-logrotate': True}))
        self.assertNotInTacFile("import Log")
        self.assertWasQuiet()

    def test_makeTAC_int_log_count(self):
        create_master.makeTAC(mkconfig(basedir='test', **{'log-count': 30}))
        self.assertInTacFile("\nmaxRotatedFiles = 30\n")
        self.assertWasQuiet()

    def test_makeTAC_str_log_count(self):
        self.assertRaises(TypeError,
                          create_master.makeTAC,
                          mkconfig(basedir='test', **{'log-count': '30'}))

    def test_makeTAC_none_log_count(self):
        create_master.makeTAC(mkconfig(basedir='test', **{'log-count': None}))
        self.assertInTacFile("\nmaxRotatedFiles = None\n")
        self.assertWasQuiet()

    def test_makeTAC_int_log_size(self):
        create_master.makeTAC(mkconfig(basedir='test', **{'log-size': 3000}))
        self.assertInTacFile("\nrotateLength = 3000\n")
        self.assertWasQuiet()

    def test_makeTAC_str_log_size(self):
        self.assertRaises(TypeError,
                          create_master.makeTAC,
                          mkconfig(basedir='test', **{'log-size': '3000'}))

    def test_makeTAC_existing_incorrect(self):
        with open(os.path.join('test', 'buildbot.tac'), 'wt') as f:
            f.write('WRONG')
        create_master.makeTAC(mkconfig(basedir='test'))
        self.assertInTacFile("WRONG")
        self.assertTrue(os.path.exists(
            os.path.join('test', 'buildbot.tac.new')))
        self.assertInStdout('not touching existing buildbot.tac')

    def test_makeTAC_existing_incorrect_quiet(self):
        with open(os.path.join('test', 'buildbot.tac'), 'wt') as f:
            f.write('WRONG')
        create_master.makeTAC(mkconfig(basedir='test', quiet=True))
        self.assertInTacFile("WRONG")
        self.assertWasQuiet()

    def test_makeTAC_existing_correct(self):
        create_master.makeTAC(mkconfig(basedir='test', quiet=True))
        create_master.makeTAC(mkconfig(basedir='test'))
        self.assertFalse(os.path.exists(
            os.path.join('test', 'buildbot.tac.new')))
        self.assertInStdout('and is correct')

    def test_makeSampleConfig(self):
        create_master.makeSampleConfig(mkconfig(basedir='test'))
        self.assertTrue(os.path.exists(
            os.path.join('test', 'master.cfg.sample')))
        self.assertInStdout('creating ')

    def test_makeSampleConfig_db(self):
        create_master.makeSampleConfig(mkconfig(basedir='test', db='XXYYZZ',
                                                quiet=True))
        with open(os.path.join('test', 'master.cfg.sample'), 'rt') as f:
            self.assertIn("XXYYZZ", f.read())
        self.assertWasQuiet()

    @defer.inlineCallbacks
    def test_createDB(self):
        setup = mock.Mock(side_effect=lambda **kwargs: defer.succeed(None))
        self.patch(connector.DBConnector, 'setup', setup)
        upgrade = mock.Mock(side_effect=lambda **kwargs: defer.succeed(None))
        self.patch(model.Model, 'upgrade', upgrade)
        yield create_master.createDB(
            mkconfig(basedir='test', quiet=True),
            _noMonkey=True)
        setup.asset_called_with(check_version=False, verbose=False)
        upgrade.assert_called_with()
        self.assertWasQuiet()
