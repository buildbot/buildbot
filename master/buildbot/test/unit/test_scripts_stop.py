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
import time

from twisted.trial import unittest

from buildbot.scripts import stop
from buildbot.test.util import dirs
from buildbot.test.util import misc
from buildbot.test.util.decorators import skipUnlessPlatformIs


def mkconfig(**kwargs):
    config = dict(quiet=False, clean=False, basedir=os.path.abspath('basedir'))
    config['no-wait'] = kwargs.pop('no_wait', False)
    config.update(kwargs)
    return config


class TestStop(misc.StdoutAssertionsMixin, dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpDirs('basedir')
        self.setUpStdoutAssertions()

    def tearDown(self):
        self.tearDownDirs()

    # tests

    def do_test_stop(self, config, kill_sequence, is_running=True, **kwargs):
        with open(os.path.join('basedir', 'buildbot.tac'), 'wt') as f:
            f.write("Application('buildmaster')")
        if is_running:
            with open("basedir/twistd.pid", 'wt') as f:
                f.write('1234')

        def sleep(t):
            self.assertTrue(kill_sequence, "unexpected sleep: %d" % t)
            what, exp_t = kill_sequence.pop(0)
            self.assertEqual((what, exp_t), ('sleep', t))
        self.patch(time, 'sleep', sleep)

        def kill(pid, signal):
            self.assertTrue(kill_sequence, "unexpected signal: %d" % signal)
            exp_sig, result = kill_sequence.pop(0)
            self.assertEqual((pid, signal), (1234, exp_sig))
            if isinstance(result, Exception):
                raise result
            else:
                return result
        self.patch(os, 'kill', kill)
        rv = stop.stop(config, **kwargs)
        self.assertEqual(kill_sequence, [])
        return rv

    @skipUnlessPlatformIs('posix')
    def test_stop_not_running(self):
        rv = self.do_test_stop(mkconfig(no_wait=True), [], is_running=False)
        self.assertInStdout('not running')
        self.assertEqual(rv, 0)

    @skipUnlessPlatformIs('posix')
    def test_stop_dead_but_pidfile_remains(self):
        rv = self.do_test_stop(mkconfig(no_wait=True),
                               [(signal.SIGTERM, OSError(3, 'No such process'))])
        self.assertEqual(rv, 0)
        self.assertFalse(os.path.exists(os.path.join('basedir', 'twistd.pid')))
        self.assertInStdout('not running')

    @skipUnlessPlatformIs('posix')
    def test_stop_dead_but_pidfile_remains_quiet(self):
        rv = self.do_test_stop(mkconfig(quiet=True, no_wait=True),
                               [(signal.SIGTERM, OSError(3, 'No such process'))],)
        self.assertEqual(rv, 0)
        self.assertFalse(os.path.exists(os.path.join('basedir', 'twistd.pid')))
        self.assertWasQuiet()

    @skipUnlessPlatformIs('posix')
    def test_stop_dead_but_pidfile_remains_wait(self):
        rv = self.do_test_stop(mkconfig(no_wait=True),
                               [(signal.SIGTERM, OSError(3, 'No such process'))
                                ],
                               wait=True)
        self.assertEqual(rv, 0)
        self.assertFalse(os.path.exists(os.path.join('basedir', 'twistd.pid')))

    @skipUnlessPlatformIs('posix')
    def test_stop_slow_death_wait(self):
        rv = self.do_test_stop(mkconfig(no_wait=True), [
            (signal.SIGTERM, None),
            ('sleep', 0.1),
            (0, None),  # polling..
            ('sleep', 1),
            (0, None),
            ('sleep', 1),
            (0, None),
            ('sleep', 1),
            (0, OSError(3, 'No such process')),
        ],
            wait=True)
        self.assertInStdout('is dead')
        self.assertEqual(rv, 0)

    @skipUnlessPlatformIs('posix')
    def test_stop_slow_death_wait_timeout(self):
        rv = self.do_test_stop(mkconfig(no_wait=True), [
            (signal.SIGTERM, None),
            ('sleep', 0.1), ] +
            [(0, None),
             ('sleep', 1), ] * 10,
            wait=True)
        self.assertInStdout('never saw process')
        self.assertEqual(rv, 1)

    @skipUnlessPlatformIs('posix')
    def test_stop_slow_death_config_wait_timeout(self):
        rv = self.do_test_stop(mkconfig(), [
            (signal.SIGTERM, None),
            ('sleep', 0.1), ] +
            [(0, None),
             ('sleep', 1), ] * 10,
        )
        self.assertInStdout('never saw process')
        self.assertEqual(rv, 1)

    @skipUnlessPlatformIs('posix')
    def test_stop_clean(self):
        rv = self.do_test_stop(mkconfig(clean=True, no_wait=True), [
            (signal.SIGUSR1, None), ], wait=False)
        self.assertInStdout('sent SIGUSR1 to process')
        self.assertEqual(rv, 0)
