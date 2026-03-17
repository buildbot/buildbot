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
from typing import Any
from typing import cast

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.clients import usersclient
from buildbot.process.users import users
from buildbot.scripts import user

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorTime

    from buildbot.util.twisted import InlineCallbacksType


class TestUsersClient(unittest.TestCase):
    class FakeUsersClient:
        def __init__(
            self, master: str, username: str = "user", passwd: str = "userpw", port: int = 0
        ) -> None:
            self.master = master
            self.port = port
            self.username = username
            self.passwd = passwd
            self.fail = False

        def send(
            self, op: Any, bb_username: Any, bb_password: Any, ids: Any, info: Any
        ) -> Deferred[None]:
            self.op = op
            self.bb_username = bb_username
            self.bb_password = bb_password
            self.ids = ids
            self.info = info
            d: Deferred[None] = defer.Deferred()
            if self.fail:
                cast("IReactorTime", reactor).callLater(0, d.errback, RuntimeError("oh noes"))
            else:
                cast("IReactorTime", reactor).callLater(0, d.callback, None)
            return d

    def setUp(self) -> None:
        def fake_UsersClient(*args: Any) -> TestUsersClient.FakeUsersClient:
            self.usersclient = self.FakeUsersClient(*args)
            return self.usersclient

        self.patch(usersclient, 'UsersClient', fake_UsersClient)

        # un-do the effects of @in_reactor
        self.patch(user, 'user', user.user._orig)  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_usersclient_send_ids(self) -> InlineCallbacksType[None]:
        yield user.user({
            "master": 'a:9990',
            "username": "x",
            "passwd": "y",
            "op": 'get',
            "bb_username": None,
            "bb_password": None,
            "ids": ['me', 'you'],
            "info": None,
        })

        c = self.usersclient
        self.assertEqual(
            (c.master, c.port, c.username, c.passwd, c.op, c.ids, c.info),
            ('a', 9990, "x", "y", 'get', ['me', 'you'], None),
        )

    @defer.inlineCallbacks
    def test_usersclient_send_update_info(self) -> InlineCallbacksType[None]:
        def _fake_encrypt(passwd: str) -> str:
            assert passwd == 'day'
            return 'ENCRY'

        self.patch(users, 'encrypt', _fake_encrypt)

        yield user.user({
            "master": 'a:9990',
            "username": "x",
            "passwd": "y",
            "op": 'update',
            "bb_username": 'bud',
            "bb_password": 'day',
            "ids": None,
            "info": [{'identifier': 'x', 'svn': 'x'}],
        })

        c = self.usersclient
        self.assertEqual(
            (
                c.master,
                c.port,
                c.username,
                c.passwd,
                c.op,
                c.bb_username,
                c.bb_password,
                c.ids,
                c.info,
            ),
            (
                'a',
                9990,
                "x",
                "y",
                'update',
                'bud',
                'ENCRY',
                None,
                [{'identifier': 'x', 'svn': 'x'}],
            ),
        )

    @defer.inlineCallbacks
    def test_usersclient_send_add_info(self) -> InlineCallbacksType[None]:
        yield user.user({
            "master": 'a:9990',
            "username": "x",
            "passwd": "y",
            "op": 'add',
            "bb_username": None,
            "bb_password": None,
            "ids": None,
            "info": [{'git': 'x <h@c>', 'irc': 'aaa'}],
        })

        c = self.usersclient
        self.assertEqual(
            (
                c.master,
                c.port,
                c.username,
                c.passwd,
                c.op,
                c.bb_username,
                c.bb_password,
                c.ids,
                c.info,
            ),
            (
                'a',
                9990,
                "x",
                "y",
                'add',
                None,
                None,
                None,
                [{'identifier': 'aaa', 'git': 'x <h@c>', 'irc': 'aaa'}],
            ),
        )
