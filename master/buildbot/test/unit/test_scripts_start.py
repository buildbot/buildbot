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

import os, sys
import twisted
from twisted.python import versions
from twisted.internet.utils import getProcessOutputAndValue
from twisted.trial import unittest
from buildbot.scripts import start
from buildbot.test.util import dirs, misc, compat

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
from twisted.python import log
from twisted.internet import reactor
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
        self.assertInStdout('not a buildmaster directory')

    def runStart(self, **config):
        args=[
                '-c',
                'from buildbot.scripts.start import start; start(%r)' % (mkconfig(**config),),
                ]
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        return getProcessOutputAndValue(sys.executable, args=args, env=env)

    def test_start_no_daemon(self):
        d = self.runStart(nodaemon=True)
        @d.addCallback
        def cb(res):
            self.assertEquals(res, ('', '', 0))
            print res
        return d

    def test_start_quiet(self):
        d = self.runStart(quiet=True)
        @d.addCallback
        def cb(res):
            self.assertEquals(res, ('', '', 0))
            print res
        return d

    @compat.skipUnlessPlatformIs('posix')
    def test_start(self):
        d = self.runStart()
        @d.addCallback
        def cb((out, err, rc)):
            self.assertEqual((rc, err), (0, ''))
            self.assertSubstring('BuildMaster is running', out)
        return d

    if twisted.version <= versions.Version('twisted', 9, 0, 0):
        test_start = test_start_quiet.skip = "Skipping due to suprious PotentialZombieWarning."

    # the remainder of this script does obscene things:
    #  - forks
    #  - shells out to tail
    #  - starts and stops the reactor
    # so testing it will be *far* more pain than is worthwhile
