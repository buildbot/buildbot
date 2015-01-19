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

from buildbot.status import builder
from buildbot.status import master
from buildbot.test.fake import fakemaster
from twisted.trial import unittest


class TestBuildStepStatus(unittest.TestCase):

    # that buildstep.BuildStepStatus is never instantiated here should tell you
    # that these classes are not well isolated!

    def setupBuilder(self, buildername, tags=None, description=None):
        self.master = fakemaster.make_master()
        self.master.basedir = '/basedir'

        b = builder.BuilderStatus(buildername, tags, self.master, description)
        b.master = self.master
        # Ackwardly, Status sets this member variable.
        b.basedir = os.path.abspath(self.mktemp())
        os.mkdir(b.basedir)
        # Otherwise, builder.nextBuildNumber is not defined.
        b.determineNextBuildNumber()
        return b

    def setupStatus(self, b):
        s = master.Status(self.master)
        b.status = s
        return s

    def testBuildStepNumbers(self):
        b = self.setupBuilder('builder_1')
        bs = b.newBuild()
        self.assertEquals(0, bs.getNumber())
        bss1 = bs.addStepWithName('step_1')
        self.assertEquals('step_1', bss1.getName())
        bss2 = bs.addStepWithName('step_2')
        self.assertEquals(0, bss1.asDict()['step_number'])
        self.assertEquals('step_2', bss2.getName())
        self.assertEquals(1, bss2.asDict()['step_number'])
        self.assertEquals([bss1, bss2], bs.getSteps())

    def testLogDict(self):
        b = self.setupBuilder('builder_1')
        self.setupStatus(b)
        bs = b.newBuild()
        bss1 = bs.addStepWithName('step_1')
        bss1.stepStarted()
        bss1.addLog('log_1')
        self.assertEquals(
            bss1.asDict()['logs'],
            [['log_1', ('http://localhost:8080/builders/builder_1/'
                        'builds/0/steps/step_1/logs/log_1')]]
        )
