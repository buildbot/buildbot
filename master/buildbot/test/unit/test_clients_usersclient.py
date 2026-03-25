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

from typing import TYPE_CHECKING
from unittest import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.spread import pb
from twisted.trial import unittest

from buildbot.clients import usersclient

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestUsersClient(unittest.TestCase):
    def setUp(self) -> None:
        # patch out some PB components and make up some mocks
        self.patch(pb, 'PBClientFactory', self._fake_PBClientFactory)
        self.patch(reactor, 'connectTCP', self._fake_connectTCP)

        self.factory = mock.Mock(name='PBClientFactory')
        self.factory.login = self._fake_login
        self.factory.login_d = defer.Deferred()

        self.remote = mock.Mock(name='PB Remote')
        self.remote.callRemote = self._fake_callRemote
        self.remote.broker.transport.loseConnection = self._fake_loseConnection

        # results
        self.conn_host: str | None = None
        self.conn_port: int | None = None
        self.lostConnection = False

    def _fake_PBClientFactory(self) -> mock.Mock:
        return self.factory

    def _fake_login(self, creds: object) -> defer.Deferred[mock.Mock]:
        return self.factory.login_d

    def _fake_connectTCP(self, host: str, port: int, factory: object) -> None:
        self.conn_host = host
        self.conn_port = port
        self.assertIdentical(factory, self.factory)
        self.factory.login_d.callback(self.remote)

    def _fake_callRemote(
        self,
        method: str,
        op: str | None,
        bb_username: str | None,
        bb_password: str | None,
        ids: list[str] | None,
        info: list[dict[str, str]] | None,
    ) -> defer.Deferred[None]:
        self.assertEqual(method, 'commandline')
        self.called_with = {
            "op": op,
            "bb_username": bb_username,
            "bb_password": bb_password,
            "ids": ids,
            "info": info,
        }
        return defer.succeed(None)

    def _fake_loseConnection(self) -> None:
        self.lostConnection = True

    def assertProcess(self, host: str, port: int, called_with: dict[str, object]) -> None:
        self.assertEqual(
            [host, port, called_with], [self.conn_host, self.conn_port, self.called_with]
        )

    @defer.inlineCallbacks
    def test_usersclient_info(self) -> InlineCallbacksType[None]:
        uc = usersclient.UsersClient('localhost', "user", "userpw", 1234)
        yield uc.send(
            'update', 'bb_user', 'hashed_bb_pass', None, [{'identifier': 'x', 'svn': 'x'}]
        )

        self.assertProcess(
            'localhost',
            1234,
            {
                "op": 'update',
                "bb_username": 'bb_user',
                "bb_password": 'hashed_bb_pass',
                "ids": None,
                "info": [{"identifier": 'x', "svn": 'x'}],
            },
        )

    @defer.inlineCallbacks
    def test_usersclient_ids(self) -> InlineCallbacksType[None]:
        uc = usersclient.UsersClient('localhost', "user", "userpw", 1234)
        yield uc.send('remove', None, None, ['x'], None)

        self.assertProcess(
            'localhost',
            1234,
            {"op": 'remove', "bb_username": None, "bb_password": None, "ids": ['x'], "info": None},
        )
