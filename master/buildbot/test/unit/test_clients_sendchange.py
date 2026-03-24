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
from unittest import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.spread import pb
from twisted.trial import unittest

from buildbot.clients import sendchange

if TYPE_CHECKING:
    from twisted.cred import credentials

    from buildbot.util.twisted import InlineCallbacksType


class Sender(unittest.TestCase):
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
        self.creds: credentials.UsernamePassword | None = None
        self.conn_host: str | None = None
        self.conn_port: int | None = None
        self.lostConnection = False
        self.added_changes: list[dict[str, Any]] = []
        self.vc_used: str | None = None

    def _fake_PBClientFactory(self) -> mock.Mock:
        return self.factory

    def _fake_login(self, creds: credentials.UsernamePassword) -> defer.Deferred[mock.Mock]:
        self.creds = creds
        return self.factory.login_d

    def _fake_connectTCP(self, host: str, port: int, factory: pb.PBClientFactory) -> None:
        self.conn_host = host
        self.conn_port = port
        self.assertIdentical(factory, self.factory)
        self.factory.login_d.callback(self.remote)

    def _fake_callRemote(self, method: str, change: dict[str, Any]) -> defer.Deferred[None]:
        self.assertEqual(method, 'addChange')
        self.added_changes.append(change)
        return defer.succeed(None)

    def _fake_loseConnection(self) -> None:
        self.lostConnection = True

    def assertProcess(
        self,
        host: str,
        port: int,
        username: bytes,
        password: bytes,
        changes: list[dict[str, Any]],
    ) -> None:
        self.assertEqual(
            [host, port, username, password, changes],
            [
                self.conn_host,
                self.conn_port,
                self.creds.username,  # type: ignore[union-attr]
                self.creds.password,  # type: ignore[union-attr]
                self.added_changes,
            ],
        )

    @defer.inlineCallbacks
    def test_send_minimal(self) -> InlineCallbacksType[None]:
        s = sendchange.Sender('localhost:1234')
        yield s.send('branch', 'rev', 'comm', ['a'])

        self.assertProcess(
            'localhost',
            1234,
            b'change',
            b'changepw',
            [
                {
                    "project": '',
                    "repository": '',
                    "who": None,
                    "files": ['a'],
                    "comments": 'comm',
                    "branch": 'branch',
                    "revision": 'rev',
                    "category": None,
                    "when": None,
                    "properties": {},
                    "revlink": '',
                    "src": None,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_send_auth(self) -> InlineCallbacksType[None]:
        s = sendchange.Sender('localhost:1234', auth=('me', 'sekrit'))
        yield s.send('branch', 'rev', 'comm', ['a'])

        self.assertProcess(
            'localhost',
            1234,
            b'me',
            b'sekrit',
            [
                {
                    "project": '',
                    "repository": '',
                    "who": None,
                    "files": ['a'],
                    "comments": 'comm',
                    "branch": 'branch',
                    "revision": 'rev',
                    "category": None,
                    "when": None,
                    "properties": {},
                    "revlink": '',
                    "src": None,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_send_full(self) -> InlineCallbacksType[None]:
        s = sendchange.Sender('localhost:1234')
        yield s.send(
            'branch',
            'rev',
            'comm',
            ['a'],
            who='me',
            category='cats',
            when=1234,
            properties={'a': 'b'},
            repository='r',
            vc='git',
            project='p',
            revlink='rl',
        )

        self.assertProcess(
            'localhost',
            1234,
            b'change',
            b'changepw',
            [
                {
                    "project": 'p',
                    "repository": 'r',
                    "who": 'me',
                    "files": ['a'],
                    "comments": 'comm',
                    "branch": 'branch',
                    "revision": 'rev',
                    "category": 'cats',
                    "when": 1234,
                    "properties": {'a': 'b'},
                    "revlink": 'rl',
                    "src": 'git',
                }
            ],
        )

    @defer.inlineCallbacks
    def test_send_files_tuple(self) -> InlineCallbacksType[None]:
        # 'buildbot sendchange' sends files as a tuple, rather than a list..
        s = sendchange.Sender('localhost:1234')
        yield s.send('branch', 'rev', 'comm', ('a', 'b'))

        self.assertProcess(
            'localhost',
            1234,
            b'change',
            b'changepw',
            [
                {
                    "project": '',
                    "repository": '',
                    "who": None,
                    "files": ['a', 'b'],
                    "comments": 'comm',
                    "branch": 'branch',
                    "revision": 'rev',
                    "category": None,
                    "when": None,
                    "properties": {},
                    "revlink": '',
                    "src": None,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_send_codebase(self) -> InlineCallbacksType[None]:
        s = sendchange.Sender('localhost:1234')
        yield s.send('branch', 'rev', 'comm', ['a'], codebase='mycb')

        self.assertProcess(
            'localhost',
            1234,
            b'change',
            b'changepw',
            [
                {
                    "project": '',
                    "repository": '',
                    "who": None,
                    "files": ['a'],
                    "comments": 'comm',
                    "branch": 'branch',
                    "revision": 'rev',
                    "category": None,
                    "when": None,
                    "properties": {},
                    "revlink": '',
                    "src": None,
                    "codebase": 'mycb',
                }
            ],
        )

    @defer.inlineCallbacks
    def test_send_unicode(self) -> InlineCallbacksType[None]:
        s = sendchange.Sender('localhost:1234')
        yield s.send(
            '\N{DEGREE SIGN}',
            '\U0001f49e',
            '\N{POSTAL MARK FACE}',
            ['\U0001f4c1'],
            project='\N{SKULL AND CROSSBONES}',
            repository='\N{SNOWMAN}',
            who='\N{THAI CHARACTER KHOMUT}',
            category='\U0001f640',
            when=1234,
            properties={'\N{LATIN SMALL LETTER A WITH MACRON}': 'b'},
            revlink='\U0001f517',
        )

        self.assertProcess(
            'localhost',
            1234,
            b'change',
            b'changepw',
            [
                {
                    "project": '\N{SKULL AND CROSSBONES}',
                    "repository": '\N{SNOWMAN}',
                    "who": '\N{THAI CHARACTER KHOMUT}',
                    "files": ['\U0001f4c1'],  # FILE FOLDER
                    "comments": '\N{POSTAL MARK FACE}',
                    "branch": '\N{DEGREE SIGN}',
                    "revision": '\U0001f49e',  # REVOLVING HEARTS
                    "category": '\U0001f640',  # WEARY CAT FACE
                    "when": 1234,
                    "properties": {'\N{LATIN SMALL LETTER A WITH MACRON}': 'b'},
                    "revlink": '\U0001f517',  # LINK SYMBOL
                    "src": None,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_send_unicode_utf8(self) -> InlineCallbacksType[None]:
        s = sendchange.Sender('localhost:1234')

        yield s.send(
            '\N{DEGREE SIGN}'.encode(),
            '\U0001f49e'.encode(),
            '\N{POSTAL MARK FACE}'.encode(),
            ['\U0001f4c1'.encode()],
            project='\N{SKULL AND CROSSBONES}'.encode(),
            repository='\N{SNOWMAN}'.encode(),
            who='\N{THAI CHARACTER KHOMUT}'.encode(),
            category='\U0001f640'.encode(),
            when=1234,
            properties={'\N{LATIN SMALL LETTER A WITH MACRON}'.encode(): 'b'},
            revlink='\U0001f517'.encode(),
        )

        self.assertProcess(
            'localhost',
            1234,
            b'change',
            b'changepw',
            [
                {
                    "project": '\N{SKULL AND CROSSBONES}',
                    "repository": '\N{SNOWMAN}',
                    "who": '\N{THAI CHARACTER KHOMUT}',
                    "files": ['\U0001f4c1'],  # FILE FOLDER
                    "comments": '\N{POSTAL MARK FACE}',
                    "branch": '\N{DEGREE SIGN}',
                    "revision": '\U0001f49e',  # REVOLVING HEARTS
                    "category": '\U0001f640',  # WEARY CAT FACE
                    "when": 1234,
                    # NOTE: not decoded!
                    "properties": {b'\xc4\x81': 'b'},
                    "revlink": '\U0001f517',  # LINK SYMBOL
                    "src": None,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_send_unicode_latin1(self) -> InlineCallbacksType[None]:
        # hand send() a bunch of latin1 strings, and expect them recoded
        # to unicode
        s = sendchange.Sender('localhost:1234', encoding='latin1')

        yield s.send(
            '\N{YEN SIGN}'.encode('latin1'),
            '\N{POUND SIGN}'.encode('latin1'),
            '\N{BROKEN BAR}'.encode('latin1'),
            ['\N{NOT SIGN}'.encode('latin1')],
            project='\N{DEGREE SIGN}'.encode('latin1'),
            repository='\N{SECTION SIGN}'.encode('latin1'),
            who='\N{MACRON}'.encode('latin1'),
            category='\N{PILCROW SIGN}'.encode('latin1'),
            when=1234,
            properties={'\N{SUPERSCRIPT ONE}'.encode('latin1'): 'b'},
            revlink='\N{INVERTED QUESTION MARK}'.encode('latin1'),
        )

        self.assertProcess(
            'localhost',
            1234,
            b'change',
            b'changepw',
            [
                {
                    "project": '\N{DEGREE SIGN}',
                    "repository": '\N{SECTION SIGN}',
                    "who": '\N{MACRON}',
                    "files": ['\N{NOT SIGN}'],
                    "comments": '\N{BROKEN BAR}',
                    "branch": '\N{YEN SIGN}',
                    "revision": '\N{POUND SIGN}',
                    "category": '\N{PILCROW SIGN}',
                    "when": 1234,
                    # NOTE: not decoded!
                    "properties": {b'\xb9': 'b'},
                    "revlink": '\N{INVERTED QUESTION MARK}',
                    "src": None,
                }
            ],
        )
