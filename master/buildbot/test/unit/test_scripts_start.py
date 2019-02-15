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

import mock

import twisted
from twisted.internet import defer
from twisted.internet.utils import getProcessOutputAndValue
from twisted.python import versions
from twisted.trial import unittest

from buildbot.scripts import start
from buildbot.test.util import dirs
from buildbot.test.util import misc
from buildbot.test.util.decorators import flaky
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
        self.setUpDirs('basedir')
        with open(os.path.join('basedir', 'buildbot.tac'), 'wt') as f:
            f.write(fake_master_tac)
        self.setUpStdoutAssertions()

    def tearDown(self):
        self.tearDownDirs()

    # tests

    def test_start_not_basedir(self):
        self.assertEqual(start.start(mkconfig(basedir='doesntexist')), 1)
        self.assertInStdout('invalid buildmaster directory')

    def runStart(self, **config):
        args = [
            '-c',
            'from buildbot.scripts.start import start; import sys; '
            'sys.exit(start(%r))' % (
                mkconfig(**config),),
        ]
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        return getProcessOutputAndValue(sys.executable, args=args, env=env)

    @defer.inlineCallbacks
    def test_start_no_daemon(self):
        (_, err, rc) = yield self.runStart(nodaemon=True)

        self.assertEqual((err, rc), (b'', 0))

    @defer.inlineCallbacks
    def test_start_quiet(self):
        res = yield self.runStart(quiet=True)

        self.assertEqual(res, (b'', b'', 0))

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

    @flaky(bugNumber=2760)
    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_start(self):
        try:
            (out, err, rc) = yield self.runStart()

            self.assertEqual((rc, err), (0, b''))
            self.assertSubstring(
                'buildmaster appears to have (re)started correctly', out)
        finally:
            # wait for the pidfile to go away after the reactor.stop
            # in buildbot.tac takes effect
            pidfile = os.path.join('basedir', 'twistd.pid')
            while os.path.exists(pidfile):
                time.sleep(0.01)

    if twisted.version <= versions.Version('twisted', 9, 0, 0):
        test_start.skip = test_start_quiet.skip = "Skipping due to suprious PotentialZombieWarning."

    # the remainder of this script does obscene things:
    #  - forks
    #  - shells out to tail
    #  - starts and stops the reactor
    # so testing it will be *far* more pain than is worthwhile
