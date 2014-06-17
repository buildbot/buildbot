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
from mock import Mock
from twisted.trial import unittest


class TestBuildStatus(unittest.TestCase):

    # that buildstep.BuildStepStatus is never instantiated here should tell you
    # that these classes are not well isolated!

    def setupBuilder(self, buildername, description=None):
        m = fakemaster.make_master()
        b = builder.BuilderStatus(buildername=buildername, tags=None,
                                  master=m, description=description)
        # Awkwardly, Status sets this member variable.
        b.basedir = os.path.abspath(self.mktemp())
        os.mkdir(b.basedir)
        # Otherwise, builder.nextBuildNumber is not defined.
        b.determineNextBuildNumber()
        # Must initialize these fields before pickling.
        b.currentBigState = 'idle'
        b.status = 'idle'
        return b

    def setupStatus(self, b):
        m = Mock()
        m.buildbotURL = 'http://buildbot:8010/'
        m.basedir = '/basedir'
        s = master.Status(m)
        b.status = s
        return s

    def testBuildCache(self):
        b = self.setupBuilder('builder_1')
        builds = []
        for i in xrange(5):
            build = b.newBuild()
            build.setProperty('propkey', 'propval%d' % i, 'test')
            builds.append(build)
            build.buildStarted(build)
            build.buildFinished()
        for build in builds:
            build2 = b.getBuild(build.number)
            self.assertTrue(build2)
            self.assertEqual(build2.number, build.number)
            self.assertEqual(build2.getProperty('propkey'),
                             'propval%d' % build.number)
        # Do another round, to make sure we're hitting the cache
        hits = b.buildCache.hits
        for build in builds:
            build2 = b.getBuild(build.number)
            self.assertTrue(build2)
            self.assertEqual(build2.number, build.number)
            self.assertEqual(build2.getProperty('propkey'),
                             'propval%d' % build.number)
            self.assertEqual(b.buildCache.hits, hits + 1)
            hits = hits + 1
