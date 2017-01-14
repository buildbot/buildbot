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
from __future__ import print_function

import stat
import time

from twisted.trial import unittest

from buildbot import config
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.package.deb import pbuilder
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


class TestDebPbuilder(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_new(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.tgz'}) +
            1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/']) +
            0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz']) +
            0)
        self.expectOutcome(result=SUCCESS, state_string='built')
        return self.runStep()

    def test_update(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.tgz'}) +
            Expect.update('stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, 0, 0]) +
            0,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--update',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz', ]) +
            0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz']) +
            0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_buildonly_and_property(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.tgz'})
            +
            Expect.update(
                'stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, int(time.time()), 0])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            + ExpectShell.log(
                'stdio',
                stdout='blah\ndpkg-genchanges  >../somefilename.changes\foo\n')
            + 0)
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('deb-changes',
                            'somefilename.changes',
                            'DebPbuilder')
        return self.runStep()

    def test_architecture(self):
        self.setupStep(pbuilder.DebPbuilder(architecture='amd64'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-amd64-buildbot.tgz'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--architecture', 'amd64'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder',
                                 '--architecture', 'amd64', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_distribution(self):
        self.setupStep(pbuilder.DebPbuilder(distribution='woody'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/woody-local-buildbot.tgz'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/woody-local-buildbot.tgz',
                                 '--distribution', 'woody',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/woody-local-buildbot.tgz'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_basetgz(self):
        self.setupStep(pbuilder.DebPbuilder(
            basetgz='/buildbot/%(distribution)s-%(architecture)s.tgz'))
        self.expectCommands(
            Expect('stat', {'file': '/buildbot/stable-local.tgz'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/buildbot/stable-local.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/buildbot/stable-local.tgz'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mirror(self):
        self.setupStep(pbuilder.DebPbuilder(mirror='http://apt:9999/debian'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.tgz'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://apt:9999/debian'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_extrapackages(self):
        self.setupStep(pbuilder.DebPbuilder(extrapackages=['buildbot']))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.tgz'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--extrapackages', 'buildbot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--extrapackages', 'buildbot'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_keyring(self):
        self.setupStep(pbuilder.DebPbuilder(keyring='/builbot/buildbot.gpg'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.tgz'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--debootstrapopts', '--keyring=/builbot/buildbot.gpg'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_components(self):
        self.setupStep(pbuilder.DebPbuilder(components='main universe'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.tgz'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--components', 'main universe'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()


class TestDebCowbuilder(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_new(self):
        self.setupStep(pbuilder.DebCowbuilder())
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.cow/'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--create',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_update(self):
        self.setupStep(pbuilder.DebCowbuilder())
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.cow/'})
            +
            Expect.update('stat', [stat.S_IFDIR, 99, 99, 1, 0, 0, 99, 0, 0, 0])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--update',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/', ])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_buildonly(self):
        self.setupStep(pbuilder.DebCowbuilder())
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.cow/'})
            +
            Expect.update(
                'stat', [stat.S_IFDIR, 99, 99, 1, 0, 0, 99, 0, int(time.time()), 0])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_update_reg(self):
        self.setupStep(pbuilder.DebCowbuilder(
            basetgz='/var/cache/pbuilder/stable-local-buildbot.cow'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.cow'})
            +
            Expect.update('stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, 0, 0])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--update',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow'])
            + 1)
        self.expectOutcome(result=FAILURE, state_string='built (failure)')
        return self.runStep()

    def test_buildonly_reg(self):
        self.setupStep(pbuilder.DebCowbuilder(
            basetgz='/var/cache/pbuilder/stable-local-buildbot.cow'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/stable-local-buildbot.cow'})
            +
            Expect.update(
                'stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, int(time.time()), 0])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow'])
            + 1)
        self.expectOutcome(result=FAILURE, state_string='built (failure)')
        return self.runStep()


class TestUbuPbuilder(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_distribution(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          pbuilder.UbuPbuilder())

    def test_new(self):
        self.setupStep(pbuilder.UbuPbuilder(distribution='oneiric'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/oneiric-local-buildbot.tgz'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/oneiric-local-buildbot.tgz',
                                 '--distribution', 'oneiric',
                                 '--mirror', 'http://archive.ubuntu.com/ubuntu/',
                                 '--components', 'main universe'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/oneiric-local-buildbot.tgz'])
            + 0)
        self.expectOutcome(result=SUCCESS, state_string='built')
        return self.runStep()


class TestUbuCowbuilder(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_distribution(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          pbuilder.UbuCowbuilder())

    def test_new(self):
        self.setupStep(pbuilder.UbuCowbuilder(distribution='oneiric'))
        self.expectCommands(
            Expect(
                'stat', {'file': '/var/cache/pbuilder/oneiric-local-buildbot.cow/'})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--create',
                                 '--basepath', '/var/cache/pbuilder/oneiric-local-buildbot.cow/',
                                 '--distribution', 'oneiric',
                                 '--mirror', 'http://archive.ubuntu.com/ubuntu/',
                                 '--components', 'main universe'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/oneiric-local-buildbot.cow/'])
            + 0)
        self.expectOutcome(result=SUCCESS, state_string='built')
        return self.runStep()
