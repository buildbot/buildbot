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
from future.utils import itervalues

import mock

from twisted.trial import unittest

from buildbot import config
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import Properties
from buildbot.process.properties import WithProperties
from buildbot.steps.shell import SetPropertyFromCommand
from buildbot.steps.shell import ShellCommand


class FakeSlaveBuilder:
    slave = None


class FakeBuildStatus:

    def __init__(self):
        self.names = []

    def getProperties(self):
        return Properties()

    def setSourceStamps(self, ss_list):
        self.ss_list = ss_list

    def setReason(self, reason):
        self.reason = reason

    def setBlamelist(self, bl):
        self.bl = bl

    def setProgress(self, p):
        self.progress = p


class FakeBuildRequest:

    def __init__(self, reason, sources, buildername):
        self.reason = reason
        self.sources = sources
        self.buildername = buildername
        self.changes = []
        self.properties = Properties()

    def mergeSourceStampsWith(self, others):
        return [source for source in itervalues(self.sources)]

    def mergeReasons(self, others):
        return self.reason


class TestShellCommandProperties(unittest.TestCase):

    def testCommand(self):
        f = BuildFactory()
        f.addStep(SetPropertyFromCommand(command=["echo", "value"], property="propname"))
        f.addStep(ShellCommand(command=["echo", WithProperties("%(propname)s")]))

        ss = mock.Mock(name="sourcestamp")
        ss.repository = 'repo'
        ss.changes = []
        ss.patch = ss.patch_info = None

        req = FakeBuildRequest("Testing", {ss.repository: ss}, None)

        b = f.newBuild([req])
        b.master = mock.Mock(name='master')
        b.build_status = FakeBuildStatus()
        b.slavebuilder = FakeSlaveBuilder()

        # This shouldn't raise an exception
        b.setupBuild(None)


class TestSetProperty(unittest.TestCase):

    def testGoodStep(self):
        f = BuildFactory()
        f.addStep(SetPropertyFromCommand(command=["echo", "value"], property="propname"))

        ss = mock.Mock(name="sourcestamp")
        ss.repository = 'repo'
        ss.changes = []
        ss.patch = ss.patch_info = None

        req = FakeBuildRequest("Testing", {ss.repository: ss}, None)

        b = f.newBuild([req])
        b.master = mock.Mock(name='master')
        b.build_status = FakeBuildStatus()
        b.slavebuilder = FakeSlaveBuilder()

        # This shouldn't raise an exception
        b.setupBuild(None)

    def testErrorBothSet(self):
        self.assertRaises(config.ConfigErrors,
                          SetPropertyFromCommand, command=["echo", "value"], property="propname", extract_fn=lambda x: {"propname": "hello"})

    def testErrorNoneSet(self):
        self.assertRaises(config.ConfigErrors,
                          SetPropertyFromCommand, command=["echo", "value"])
