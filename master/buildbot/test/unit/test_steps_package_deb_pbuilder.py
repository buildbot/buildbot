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

import stat
import time

from buildbot.status.results import SUCCESS
from buildbot.steps.package.deb import pbuilder
from buildbot.test.fake.remotecommand import Expect, ExpectShell
from buildbot.test.util import steps
from twisted.trial import unittest
from buildbot import config

class TestDebPbuilder(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success_new(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(
            Expect('stat', {'file': '/var/cache/pbuilder/stable-ownarch-buildbot.tgz'})
            #+ Expect.update('stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, ])
            #ExpectShell(workdir='wkdir', usePTY='slave-config',
            #        command=['lintian', '-v', 'foo_0.23_i386.changes'])
            +1,
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                    command=['sudo', '/usr/sbin/pbuilder', '--create', '--basetgz',
                             '/var/cache/pbuilder/stable-ownarch-buildbot.tgz',
                             '--distribution', 'stable', '--mirror',
                             'http://cdn.debian.net/debian/'])
            +0,
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                    command=['pdebuild', '--buildresult', '.', '--',
                             '--buildresult', '.', '--basetgz',
                             '/var/cache/pbuilder/stable-ownarch-buildbot.tgz'])
            +0)
        self.expectOutcome(result=SUCCESS, status_text=['pdebuild'])
        return self.runStep()

    def test_success_update(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(            
            Expect('stat', {'file': '/var/cache/pbuilder/stable-ownarch-buildbot.tgz'})
            + Expect.update('stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, 0, 0])
            +0,     
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                    command=['sudo', '/usr/sbin/pbuilder', '--update', '--basetgz',
                             '/var/cache/pbuilder/stable-ownarch-buildbot.tgz'])
            +0,
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                    command=['pdebuild', '--buildresult', '.', '--',
                             '--buildresult', '.', '--basetgz',
                             '/var/cache/pbuilder/stable-ownarch-buildbot.tgz'])
            +0)
        self.expectOutcome(result=SUCCESS, status_text=['pdebuild'])
        return self.runStep()

    def test_success(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(
            Expect('stat', {'file': '/var/cache/pbuilder/stable-ownarch-buildbot.tgz'})
            + Expect.update('stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, int(time.time()), 0])
            +0,
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                    command=['pdebuild', '--buildresult', '.', '--',
                             '--buildresult', '.', '--basetgz',
                             '/var/cache/pbuilder/stable-ownarch-buildbot.tgz'])
            +0)
        self.expectOutcome(result=SUCCESS, status_text=['pdebuild'])
        return self.runStep()
