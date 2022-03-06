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

from collections import OrderedDict

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.steps.package.rpm import rpmbuild
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin


class RpmBuild(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_no_specfile(self):
        with self.assertRaises(config.ConfigErrors):
            rpmbuild.RpmBuild()

    def test_success(self):
        self.setup_step(rpmbuild.RpmBuild(specfile="foo.spec", dist=".el5"))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command='rpmbuild --define "_topdir '
                        '`pwd`" --define "_builddir `pwd`" --define "_rpmdir '
                        '`pwd`" --define "_sourcedir `pwd`" --define "_specdir '
                        '`pwd`" --define "_srcrpmdir `pwd`" --define "dist .el5" '
                        '-ba foo.spec')
            .stdout('lalala')
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='RPMBUILD')
        return self.run_step()

    @mock.patch('builtins.open', mock.mock_open())
    def test_autoRelease(self):
        self.setup_step(rpmbuild.RpmBuild(specfile="foo.spec", autoRelease=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command='rpmbuild --define "_topdir '
                        '`pwd`" --define "_builddir `pwd`" --define "_rpmdir `pwd`" '
                        '--define "_sourcedir `pwd`" --define "_specdir `pwd`" '
                        '--define "_srcrpmdir `pwd`" --define "_release 0" '
                        '--define "dist .el6" -ba foo.spec')
            .stdout('Your code has been rated at 10/10')
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='RPMBUILD')
        return self.run_step()

    def test_define(self):
        defines = [("a", "1"), ("b", "2")]
        self.setup_step(rpmbuild.RpmBuild(specfile="foo.spec",
                                         define=OrderedDict(defines)))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command='rpmbuild --define "_topdir '
                        '`pwd`" --define "_builddir `pwd`" --define "_rpmdir '
                        '`pwd`" --define "_sourcedir `pwd`" --define '
                        '"_specdir `pwd`" --define "_srcrpmdir `pwd`" '
                        '--define "a 1" --define "b 2" --define "dist .el6" '
                        '-ba foo.spec')
            .stdout('Your code has been rated at 10/10')
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='RPMBUILD')
        return self.run_step()

    def test_define_none(self):
        self.setup_step(rpmbuild.RpmBuild(specfile="foo.spec", define=None))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command='rpmbuild --define "_topdir '
                        '`pwd`" --define "_builddir `pwd`" --define "_rpmdir '
                        '`pwd`" --define "_sourcedir `pwd`" --define '
                        '"_specdir `pwd`" --define "_srcrpmdir `pwd`" '
                        '--define "dist .el6" -ba foo.spec')
            .stdout('Your code has been rated at 10/10')
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='RPMBUILD')
        return self.run_step()

    @defer.inlineCallbacks
    def test_renderable_dist(self):
        self.setup_step(rpmbuild.RpmBuild(specfile="foo.spec",
                                         dist=Interpolate('%(prop:renderable_dist)s')))
        self.properties.setProperty('renderable_dist', '.el7', 'test')
        self.expect_commands(
            ExpectShell(workdir='wkdir', command='rpmbuild --define "_topdir '
                        '`pwd`" --define "_builddir `pwd`" --define "_rpmdir '
                        '`pwd`" --define "_sourcedir `pwd`" --define "_specdir '
                        '`pwd`" --define "_srcrpmdir `pwd`" --define "dist .el7" '
                        '-ba foo.spec')
            .stdout('lalala')
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='RPMBUILD')
        yield self.run_step()
