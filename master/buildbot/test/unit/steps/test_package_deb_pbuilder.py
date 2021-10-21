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

from twisted.trial import unittest

from buildbot import config
from buildbot.process.properties import Interpolate
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.package.deb import pbuilder
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.fake.remotecommand import ExpectStat
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin


class TestDebPbuilder(steps.BuildStepMixin, TestReactorMixin,
                      unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_new(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS, state_string='built')
        return self.runStep()

    def test_update(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .add(Expect.update('stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, 0, 0]))
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--update',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz', ])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_buildonly_and_property(self):
        self.setupStep(pbuilder.DebPbuilder())
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .add(Expect.update(
                'stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, int(time.time()), 0]))
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .add(ExpectShell.log(
                'stdio',
                stdout='blah\ndpkg-genchanges  >../somefilename.changes\foo\n'))
            .add(0))
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('deb-changes',
                            'somefilename.changes',
                            'DebPbuilder')
        return self.runStep()

    def test_architecture(self):
        self.setupStep(pbuilder.DebPbuilder(architecture='amd64'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-amd64-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--architecture', 'amd64'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder',
                                 '--architecture', 'amd64', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_architecture_renderable(self):
        self.setupStep(pbuilder.DebPbuilder(architecture=Interpolate('amd64')))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-amd64-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--architecture', 'amd64'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder',
                                 '--architecture', 'amd64', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_distribution(self):
        self.setupStep(pbuilder.DebPbuilder(distribution='woody'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/woody-local-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/woody-local-buildbot.tgz',
                                 '--distribution', 'woody',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/woody-local-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_basetgz(self):
        self.setupStep(pbuilder.DebPbuilder(basetgz='/buildbot/stable-local.tgz'))
        self.expectCommands(
            ExpectStat(file='/buildbot/stable-local.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/buildbot/stable-local.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/buildbot/stable-local.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mirror(self):
        self.setupStep(pbuilder.DebPbuilder(mirror='http://apt:9999/debian'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://apt:9999/debian'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_extrapackages(self):
        self.setupStep(pbuilder.DebPbuilder(extrapackages=['buildbot']))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--extrapackages', 'buildbot'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--extrapackages', 'buildbot'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_keyring(self):
        self.setupStep(pbuilder.DebPbuilder(keyring='/builbot/buildbot.gpg'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--debootstrapopts', '--keyring=/builbot/buildbot.gpg'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_components(self):
        self.setupStep(pbuilder.DebPbuilder(components='main universe'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--components', 'main universe'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_othermirror(self):
        self.setupStep(pbuilder.DebPbuilder(othermirror=['http://apt:9999/debian']))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--othermirror', 'http://apt:9999/debian'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()


class TestDebCowbuilder(steps.BuildStepMixin, TestReactorMixin,
                        unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_new(self):
        self.setupStep(pbuilder.DebCowbuilder())
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow/')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--create',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_update(self):
        self.setupStep(pbuilder.DebCowbuilder())
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow/')
            .add(Expect.update('stat', [stat.S_IFDIR, 99, 99, 1, 0, 0, 99, 0, 0, 0]))
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--update',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/', ])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_buildonly(self):
        self.setupStep(pbuilder.DebCowbuilder())
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow/')
            .add(Expect.update('stat', [stat.S_IFDIR, 99, 99, 1, 0, 0, 99, 0, int(time.time()), 0]))
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            .add(0))
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_update_reg(self):
        self.setupStep(pbuilder.DebCowbuilder(
            basetgz='/var/cache/pbuilder/stable-local-buildbot.cow'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow')
            .add(Expect.update('stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, 0, 0]))
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--update',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow'])
            .add(1))
        self.expectOutcome(result=FAILURE, state_string='built (failure)')
        return self.runStep()

    def test_buildonly_reg(self):
        self.setupStep(pbuilder.DebCowbuilder(
            basetgz='/var/cache/pbuilder/stable-local-buildbot.cow'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow')
            .add(Expect.update(
                'stat', [stat.S_IFREG, 99, 99, 1, 0, 0, 99, 0, int(time.time()), 0]))
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow'])
            .add(1))
        self.expectOutcome(result=FAILURE, state_string='built (failure)')
        return self.runStep()


class TestUbuPbuilder(steps.BuildStepMixin, TestReactorMixin,
                      unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_distribution(self):
        with self.assertRaises(config.ConfigErrors):
            pbuilder.UbuPbuilder()

    def test_new(self):
        self.setupStep(pbuilder.UbuPbuilder(distribution='oneiric'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/oneiric-local-buildbot.tgz')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/oneiric-local-buildbot.tgz',
                                 '--distribution', 'oneiric',
                                 '--mirror', 'http://archive.ubuntu.com/ubuntu/',
                                 '--components', 'main universe'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/oneiric-local-buildbot.tgz'])
            .add(0))
        self.expectOutcome(result=SUCCESS, state_string='built')
        return self.runStep()


class TestUbuCowbuilder(steps.BuildStepMixin, TestReactorMixin,
                        unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_distribution(self):
        with self.assertRaises(config.ConfigErrors):
            pbuilder.UbuCowbuilder()

    def test_new(self):
        self.setupStep(pbuilder.UbuCowbuilder(distribution='oneiric'))
        self.expectCommands(
            ExpectStat(file='/var/cache/pbuilder/oneiric-local-buildbot.cow/')
            .add(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--create',
                                 '--basepath', '/var/cache/pbuilder/oneiric-local-buildbot.cow/',
                                 '--distribution', 'oneiric',
                                 '--mirror', 'http://archive.ubuntu.com/ubuntu/',
                                 '--components', 'main universe'])
            .add(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/oneiric-local-buildbot.cow/'])
            .add(0))
        self.expectOutcome(result=SUCCESS, state_string='built')
        return self.runStep()
