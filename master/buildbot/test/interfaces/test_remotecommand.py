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

from buildbot.process import buildstep
from buildbot.test.util import interfaces
from buildbot.test.fake import remotecommand
from twisted.trial import unittest

# NOTE:
#
# This interface is considered private to Buildbot and may change without
# warning in future versions.

class Tests(interfaces.InterfaceTests):

    def makeRemoteCommand(self, name, args):
        raise NotImplementedError

    def test_signature_useLog(self):
        rc = self.makeRemoteCommand('ping', {'arg':'val'})
        @self.assertArgSpecMatches(rc.useLog)
        def useLog(self, log, closeWhenFinished=False, logfileName=None):
            pass

    def test_signature_useLogDelayed(self):
        rc = self.makeRemoteCommand('ping', {'arg':'val'})
        @self.assertArgSpecMatches(rc.useLogDelayed)
        def useLogDelayed(self, logfileName, activateCallBack,
                closeWhenFinished=False):
            pass

    def test_signature_run(self):
        rc = self.makeRemoteCommand('ping', {'arg':'val'})
        @self.assertArgSpecMatches(rc.run)
        def run(self, step, remote):
            pass


class RealTests(Tests):
    pass


class TestRunCommand(unittest.TestCase, RealTests):

    def makeRemoteCommand(self, name, args):
        return buildstep.RemoteCommand(name, args)


class TestFakeRunCommand(unittest.TestCase, Tests):

    def makeRemoteCommand(self, name, args):
        return remotecommand.FakeRemoteCommand(name, args)

