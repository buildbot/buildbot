import os

from buildbot.status import builder
#from buildbot.util import json
from mock import Mock

from twisted.trial import unittest

class TestBuildStepStatus(unittest.TestCase):
    def setupBuilder(self, buildername, category=None):
        b = builder.BuilderStatus(buildername=buildername, category=category)
        # Ackwardly, Status sets this member variable.
        b.basedir = os.path.abspath(self.mktemp())
        os.mkdir(b.basedir)
        # Otherwise, builder.nextBuildNumber is not defined.
        b.determineNextBuildNumber()
        return b

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
