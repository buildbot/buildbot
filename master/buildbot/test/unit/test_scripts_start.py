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
from twisted.trial import unittest
from buildbot.scripts import start
from buildbot.test.util import dirs, misc

def mkconfig(**kwargs):
    config = dict(quiet=False, basedir=os.path.abspath('basedir'))
    config.update(kwargs)
    return config

fake_master_tac = """\
from twisted.application import service
from twisted.python import log
from twisted.internet import reactor
application = service.Application('highscore')
class App(service.Service):
    def startService(self):
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

    # the remainder of this script does obscene things:
    #  - forks
    #  - shells out to tail
    #  - starts and stops the reactor
    # so testing it will be *far* more pain than is worthwhile
