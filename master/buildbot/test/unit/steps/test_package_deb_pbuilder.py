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

import time

from twisted.trial import unittest

from buildbot import config
from buildbot.process.properties import Interpolate
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.package.deb import pbuilder
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.steps import TestBuildStepMixin


class TestDebPbuilder(TestBuildStepMixin, TestReactorMixin,
                      unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_new(self):
        self.setup_step(pbuilder.DebPbuilder())
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='built')
        return self.run_step()

    def test_update(self):
        self.setup_step(pbuilder.DebPbuilder())
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .stat_file()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--update',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz', ])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_buildonly_and_property(self):
        self.setup_step(pbuilder.DebPbuilder())
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .stat_file(mtime=int(time.time()))
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .stdout('blah\ndpkg-genchanges  >../somefilename.changes\foo\n')
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        self.expect_property('deb-changes',
                            'somefilename.changes',
                            'DebPbuilder')
        return self.run_step()

    def test_architecture(self):
        self.setup_step(pbuilder.DebPbuilder(architecture='amd64'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-amd64-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--architecture', 'amd64'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder',
                                 '--architecture', 'amd64', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_architecture_renderable(self):
        self.setup_step(pbuilder.DebPbuilder(architecture=Interpolate('amd64')))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-amd64-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--architecture', 'amd64'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder',
                                 '--architecture', 'amd64', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-amd64-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_distribution(self):
        self.setup_step(pbuilder.DebPbuilder(distribution='woody'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/woody-local-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/woody-local-buildbot.tgz',
                                 '--distribution', 'woody',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/woody-local-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_basetgz(self):
        self.setup_step(pbuilder.DebPbuilder(basetgz='/buildbot/stable-local.tgz'))
        self.expect_commands(
            ExpectStat(file='/buildbot/stable-local.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/buildbot/stable-local.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/buildbot/stable-local.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mirror(self):
        self.setup_step(pbuilder.DebPbuilder(mirror='http://apt:9999/debian'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://apt:9999/debian'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_extrapackages(self):
        self.setup_step(pbuilder.DebPbuilder(extrapackages=['buildbot']))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--extrapackages', 'buildbot'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--extrapackages', 'buildbot'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_keyring(self):
        self.setup_step(pbuilder.DebPbuilder(keyring='/builbot/buildbot.gpg'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--debootstrapopts', '--keyring=/builbot/buildbot.gpg'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_components(self):
        self.setup_step(pbuilder.DebPbuilder(components='main universe'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--components', 'main universe'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_othermirror(self):
        self.setup_step(pbuilder.DebPbuilder(othermirror=['http://apt:9999/debian']))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/',
                                 '--othermirror', 'http://apt:9999/debian'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/stable-local-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()


class TestDebCowbuilder(TestBuildStepMixin, TestReactorMixin,
                        unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_new(self):
        self.setup_step(pbuilder.DebCowbuilder())
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow/')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--create',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/',
                                 '--distribution', 'stable',
                                 '--mirror', 'http://cdn.debian.net/debian/'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_update(self):
        self.setup_step(pbuilder.DebCowbuilder())
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow/')
            .stat_dir()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--update',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/', ])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_buildonly(self):
        self.setup_step(pbuilder.DebCowbuilder())
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow/')
            .stat_dir(mtime=int(time.time()))
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow/'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_update_reg(self):
        self.setup_step(pbuilder.DebCowbuilder(
            basetgz='/var/cache/pbuilder/stable-local-buildbot.cow'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow')
            .stat_file()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--update',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow'])
            .exit(1))
        self.expect_outcome(result=FAILURE, state_string='built (failure)')
        return self.run_step()

    def test_buildonly_reg(self):
        self.setup_step(pbuilder.DebCowbuilder(
            basetgz='/var/cache/pbuilder/stable-local-buildbot.cow'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/stable-local-buildbot.cow')
            .stat_file(mtime=int(time.time()))
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/stable-local-buildbot.cow'])
            .exit(1))
        self.expect_outcome(result=FAILURE, state_string='built (failure)')
        return self.run_step()


class TestUbuPbuilder(TestBuildStepMixin, TestReactorMixin,
                      unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_no_distribution(self):
        with self.assertRaises(config.ConfigErrors):
            pbuilder.UbuPbuilder()

    def test_new(self):
        self.setup_step(pbuilder.UbuPbuilder(distribution='oneiric'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/oneiric-local-buildbot.tgz')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/pbuilder', '--create',
                                 '--basetgz', '/var/cache/pbuilder/oneiric-local-buildbot.tgz',
                                 '--distribution', 'oneiric',
                                 '--mirror', 'http://archive.ubuntu.com/ubuntu/',
                                 '--components', 'main universe'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/pbuilder', '--', '--buildresult', '.',
                                 '--basetgz', '/var/cache/pbuilder/oneiric-local-buildbot.tgz'])
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='built')
        return self.run_step()


class TestUbuCowbuilder(TestBuildStepMixin, TestReactorMixin,
                        unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_no_distribution(self):
        with self.assertRaises(config.ConfigErrors):
            pbuilder.UbuCowbuilder()

    def test_new(self):
        self.setup_step(pbuilder.UbuCowbuilder(distribution='oneiric'))
        self.expect_commands(
            ExpectStat(file='/var/cache/pbuilder/oneiric-local-buildbot.cow/')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['sudo', '/usr/sbin/cowbuilder', '--create',
                                 '--basepath', '/var/cache/pbuilder/oneiric-local-buildbot.cow/',
                                 '--distribution', 'oneiric',
                                 '--mirror', 'http://archive.ubuntu.com/ubuntu/',
                                 '--components', 'main universe'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['pdebuild', '--buildresult', '.',
                                 '--pbuilder', '/usr/sbin/cowbuilder', '--', '--buildresult', '.',
                                 '--basepath', '/var/cache/pbuilder/oneiric-local-buildbot.cow/'])
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='built')
        return self.run_step()
