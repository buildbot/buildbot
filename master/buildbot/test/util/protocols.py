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
from __future__ import annotations

from typing import Any

from buildbot.test.util import interfaces


class ConnectionInterfaceTest(interfaces.InterfaceTests):
    conn: Any

    def setUp(self) -> None:
        # subclasses must set self.conn in this method
        raise NotImplementedError

    def test_sig_notifyOnDisconnect(self) -> None:
        @self.assertArgSpecMatches(self.conn.notifyOnDisconnect)
        def notifyOnDisconnect(self: Any, cb: Any) -> None:
            pass

    def test_sig_loseConnection(self) -> None:
        @self.assertArgSpecMatches(self.conn.loseConnection)
        def loseConnection(self: Any) -> None:
            pass

    def test_sig_remotePrint(self) -> None:
        @self.assertArgSpecMatches(self.conn.remotePrint)
        def remotePrint(self: Any, message: Any) -> None:
            pass

    def test_sig_remoteGetWorkerInfo(self) -> None:
        @self.assertArgSpecMatches(self.conn.remoteGetWorkerInfo)
        def remoteGetWorkerInfo(self: Any) -> None:
            pass

    def test_sig_remoteSetBuilderList(self) -> None:
        @self.assertArgSpecMatches(self.conn.remoteSetBuilderList)
        def remoteSetBuilderList(self: Any, builders: Any) -> None:
            pass

    def test_sig_remoteStartCommand(self) -> None:
        @self.assertArgSpecMatches(self.conn.remoteStartCommand)
        def remoteStartCommand(
            self: Any,
            remoteCommand: Any,
            builderName: Any,
            commandId: Any,
            commandName: Any,
            args: Any,
        ) -> None:
            pass

    def test_sig_remoteShutdown(self) -> None:
        @self.assertArgSpecMatches(self.conn.remoteShutdown)
        def remoteShutdown(self: Any) -> None:
            pass

    def test_sig_remoteStartBuild(self) -> None:
        @self.assertArgSpecMatches(self.conn.remoteStartBuild)
        def remoteStartBuild(self: Any, builderName: Any) -> None:
            pass

    def test_sig_remoteInterruptCommand(self) -> None:
        @self.assertArgSpecMatches(self.conn.remoteInterruptCommand)
        def remoteInterruptCommand(builderName: Any, commandId: Any, why: Any) -> None:
            pass
