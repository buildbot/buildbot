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

import os
import time
import signal
from twisted.trial import unittest
from buildbot.scripts import clean
from buildbot.test.util import dirs, misc, compat

def mkconfig(**kwargs):
    config = dict(quiet=False, basedir=os.path.abspath('basedir'))
    config.update(kwargs)
    return config

class TestCleanShutdown(misc.StdoutAssertionsMixin, dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpDirs('basedir')
        self.setUpStdoutAssertions()

    def tearDown(self):
        self.tearDownDirs()

    # tests

    def do_test_clean(self, config, kill_sequence, is_running=True, **kwargs):
        with open(os.path.join('basedir', 'buildbot.tac'), 'wt') as f:
            f.write("Application('buildmaster')")
        if is_running:
            with open("basedir/twistd.pid", 'wt') as f:
                f.write('1234')
        def sleep(t):
            what, exp_t = kill_sequence.pop(0)
            self.assertEqual((what, exp_t), ('sleep', t))
        self.patch(time, 'sleep', sleep)
        def kill(pid, signal):
            exp_sig, result = kill_sequence.pop(0)
            self.assertEqual((pid,signal), (1234,exp_sig))
            if isinstance(result, Exception):
                raise result
            else:
                return result
        self.patch(os, 'kill', kill)
        rv = clean.clean(config, **kwargs)
        self.assertEqual(kill_sequence, [])
        return rv

    @compat.skipUnlessPlatformIs('posix')
    def test_clean_not_running(self):
        rv = self.do_test_clean(mkconfig(), [], is_running=False)
        self.assertInStdout('not running')
        self.assertEqual(rv, 0)
