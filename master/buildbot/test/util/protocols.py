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

from buildbot.test.util import interfaces


class ConnectionInterfaceTest(interfaces.InterfaceTests):

    def setUp(self):
        # subclasses must set self.conn in this method
        raise NotImplementedError

    def test_sig_notifyOnDisconnect(self):
        @self.assertArgSpecMatches(self.conn.notifyOnDisconnect)
        def notifyOnDisconnect(self, cb):
            pass

    def test_sig_loseConnection(self):
        @self.assertArgSpecMatches(self.conn.loseConnection)
        def loseConnection(self):
            pass

    def test_sig_remotePrint(self):
        @self.assertArgSpecMatches(self.conn.remotePrint)
        def remotePrint(self, message):
            pass

    def test_sig_remoteGetWorkerInfo(self):
        @self.assertArgSpecMatches(self.conn.remoteGetWorkerInfo)
        def remoteGetWorkerInfo(self):
            pass

    def test_sig_remoteSetBuilderList(self):
        @self.assertArgSpecMatches(self.conn.remoteSetBuilderList)
        def remoteSetBuilderList(self, builders):
            pass

    def test_sig_remoteStartCommand(self):
        @self.assertArgSpecMatches(self.conn.remoteStartCommand)
        def remoteStartCommand(self, remoteCommand, builderName, commandId,
                               commandName, args):
            pass

    def test_sig_remoteShutdown(self):
        @self.assertArgSpecMatches(self.conn.remoteShutdown)
        def remoteShutdown(self):
            pass

    def test_sig_remoteStartBuild(self):
        @self.assertArgSpecMatches(self.conn.remoteStartBuild)
        def remoteStartBuild(self, builderName):
            pass

    def test_sig_remoteInterruptCommand(self):
        @self.assertArgSpecMatches(self.conn.remoteInterruptCommand)
        def remoteInterruptCommand(builderName, commandId, why):
            pass
