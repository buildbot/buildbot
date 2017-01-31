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
from __future__ import division
from __future__ import print_function

import os
import sys
import time

import twisted
from twisted.internet.utils import getProcessOutputAndValue
from twisted.python import versions
from twisted.trial import unittest

from buildbot.scripts import start
from buildbot.test.util import dirs
from buildbot.test.util import misc
from buildbot.test.util.decorators import flaky
from buildbot.test.util.decorators import skipIfPythonVersionIsLess
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
        service.Service.startService(self)
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
            'from buildbot.scripts.start import start; start(%r)' % (
                mkconfig(**config),),
        ]
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        return getProcessOutputAndValue(sys.executable, args=args, env=env)

    @skipIfPythonVersionIsLess((2, 7))
    def test_start_no_daemon(self):
        d = self.runStart(nodaemon=True)

        @d.addCallback
        def cb(res):
            self.assertEqual(res, (b'', b'', 0))
            print(res)
        return d

    @skipIfPythonVersionIsLess((2, 7))
    def test_start_quiet(self):
        d = self.runStart(quiet=True)

        @d.addCallback
        def cb(res):
            self.assertEqual(res, (b'', b'', 0))
            print(res)
        return d

    @flaky(bugNumber=2760)
    @skipUnlessPlatformIs('posix')
    def test_start(self):
        d = self.runStart()

        @d.addCallback
        def cb(xxx_todo_changeme):
            (out, err, rc) = xxx_todo_changeme
            self.assertEqual((rc, err), (0, ''))
            self.assertSubstring('BuildMaster is running', out)

        @d.addBoth
        def flush(x):
            # wait for the pidfile to go away after the reactor.stop
            # in buildbot.tac takes effect
            pidfile = os.path.join('basedir', 'twistd.pid')
            while os.path.exists(pidfile):
                time.sleep(0.01)
            return x

        return d

    if twisted.version <= versions.Version('twisted', 9, 0, 0):
        test_start.skip = test_start_quiet.skip = "Skipping due to suprious PotentialZombieWarning."

    # the remainder of this script does obscene things:
    #  - forks
    #  - shells out to tail
    #  - starts and stops the reactor
    # so testing it will be *far* more pain than is worthwhile
