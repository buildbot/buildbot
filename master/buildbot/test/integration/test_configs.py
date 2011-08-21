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
from twisted.python import util
from twisted.trial import unittest
from buildbot.test.util import dirs
from buildbot.scripts import runner
from buildbot.master import BuildMaster

class SampleCfg(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpDirs('basedir')

    def tearDown(self):
        self.tearDownDirs()

    def test_config(self):
        filename = util.sibpath(runner.__file__, 'sample.cfg')
        basedir = os.path.abspath('basedir')
        master = BuildMaster(basedir, filename)
        return master.loadConfig(open(filename), checkOnly=True)
    test_config.skip = "instantiating the master does too much" # TODO
