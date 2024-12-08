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
import sys
import time
from unittest import mock

from twisted.internet import defer
from twisted.internet.utils import getProcessOutputAndValue
from twisted.trial import unittest

from buildbot.scripts import start
from buildbot.test.util import dirs
from buildbot.test.util import misc
from buildbot.test.util.decorators import skipUnlessPlatformIs


def mkconfig(**kwargs):
    config = {
        'quiet': False,
        'basedir': os.path.abspath('basedir'),
        'nodaemon': False,
    }
    config.update(kwargs)
    return config


fake_master_tac = """\
from twisted.application import service
from twisted.internet import reactor
from twisted.python import log
application = service.Application('highscore')
class App(service.Service):
    def startService(self):
        super().startService()
        log.msg("BuildMaster is running") # heh heh heh
        reactor.callLater(0, reactor.stop)
app = App()
app.setServiceParent(application)
# isBuildmasterDir wants to see this -> Application('buildmaster')
"""


class TestStart(misc.StdoutAssertionsMixin, dirs.DirsMixin, unittest.TestCase):
    def setUp(self):
        # On slower machines with high CPU oversubscription this test may take longer to run than
        # the default timeout.
        self.timeout = 20

        self.setUpDirs('basedir')
        with open(os.path.join('basedir', 'buildbot.tac'), "w", encoding='utf-8') as f:
            f.write(fake_master_tac)
        self.setUpStdoutAssertions()

    # tests

    def test_start_not_basedir(self):
        self.assertEqual(start.start(mkconfig(basedir='doesntexist')), 1)
        self.assertInStdout('invalid buildmaster directory')

    def runStart(self, **config):
        args = [
            '-c',
            'from buildbot.scripts.start import start; import sys; '
            f'sys.exit(start({mkconfig(**config)!r}))',
        ]
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        return getProcessOutputAndValue(sys.executable, args=args, env=env)

    def assert_stderr_ok(self, err):
        lines = err.split(b'\n')
        good_warning_parts = [b'32-bit Python on a 64-bit', b'cryptography.hazmat.bindings']
        for line in lines:
            is_line_good = False
            if line == b'':
                is_line_good = True
            else:
                for part in good_warning_parts:
                    if part in line:
                        is_line_good = True
                        break
            if not is_line_good:
                self.assertEqual(err, b'')  # not valid warning

    @defer.inlineCallbacks
    def test_start_no_daemon(self):
        (_, err, rc) = yield self.runStart(nodaemon=True)
        self.assert_stderr_ok(err)
        self.assertEqual(rc, 0)

    @defer.inlineCallbacks
    def test_start_quiet(self):
        res = yield self.runStart(quiet=True)

        self.assertEqual(res[0], b'')
        self.assert_stderr_ok(res[1])
        self.assertEqual(res[2], 0)

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_start_timeout_nonnumber(self):
        (out, err, rc) = yield self.runStart(start_timeout='a')

        self.assertEqual((rc, err), (1, b''))
        self.assertSubstring(b'Start timeout must be a number\n', out)

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_start_timeout_number_string(self):
        # integer values from command-line options come in as strings
        res = yield self.runStart(start_timeout='10')

        self.assertEqual(res, (mock.ANY, b'', 0))

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_start(self):
        try:
            (out, err, rc) = yield self.runStart()

            self.assertEqual((rc, err), (0, b''))
            self.assertSubstring(b'buildmaster appears to have (re)started correctly', out)
        finally:
            # wait for the pidfile to go away after the reactor.stop
            # in buildbot.tac takes effect
            pidfile = os.path.join('basedir', 'twistd.pid')
            while os.path.exists(pidfile):
                time.sleep(0.01)

    # the remainder of this script does obscene things:
    #  - forks
    #  - shells out to tail
    #  - starts and stops the reactor
    # so testing it will be *far* more pain than is worthwhile
