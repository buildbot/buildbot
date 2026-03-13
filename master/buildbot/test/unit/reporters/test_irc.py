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

import platform
import sys
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from twisted.application import internet
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import ConfigErrors
from buildbot.process.properties import Interpolate
from buildbot.process.results import ALL_RESULTS
from buildbot.process.results import SUCCESS
from buildbot.reporters import irc
from buildbot.reporters import words
from buildbot.test.unit.reporters.test_words import ContactMixin
from buildbot.test.util import config
from buildbot.util import service

if TYPE_CHECKING:
    from buildbot.reporters.irc import IrcStatusBot
    from buildbot.reporters.irc import IrcStatusFactory
    from buildbot.util.twisted import InlineCallbacksType


class TestIrcContact(ContactMixin, unittest.TestCase):
    channelClass = irc.IRCChannel
    contactClass = irc.IRCContact

    def patch_act(self) -> None:
        self.actions = []  # type: ignore[var-annotated]

        def act(msg: str) -> None:
            self.actions.append(msg)

        self.contact.act = act  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_op_required_authz(self) -> InlineCallbacksType[None]:
        self.bot.authz = self.bot.expand_authz({('mute', 'unmute'): [self.USER]})
        self.bot.getChannelOps = lambda channel: ['channelop']  # type: ignore[attr-defined]
        self.assertFalse((yield self.contact.op_required('mute')))  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_op_required_operator(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: [self.USER]  # type: ignore[attr-defined]
        self.assertFalse((yield self.contact.op_required('command')))  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_op_required_unauthorized(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: ['channelop']  # type: ignore[attr-defined]
        self.assertTrue((yield self.contact.op_required('command')))  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_command_mute(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: [self.USER]  # type: ignore[attr-defined]
        yield self.do_test_command('mute')
        self.assertTrue(self.contact.channel.muted)

    @defer.inlineCallbacks
    def test_command_mute_unauthorized(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: []  # type: ignore[attr-defined]
        yield self.do_test_command('mute')
        self.assertFalse(self.contact.channel.muted)
        self.assertIn("blah, blah", self.sent[0])

    @defer.inlineCallbacks
    def test_command_unmute(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: [self.USER]  # type: ignore[attr-defined]
        self.contact.channel.muted = True
        yield self.do_test_command('unmute')
        self.assertFalse(self.contact.channel.muted)

    @defer.inlineCallbacks
    def test_command_unmute_unauthorized(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: []  # type: ignore[attr-defined]
        self.contact.channel.muted = True
        yield self.do_test_command('unmute')
        self.assertTrue(self.contact.channel.muted)

    @defer.inlineCallbacks
    def test_command_unmute_not_muted(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: [self.USER]  # type: ignore[attr-defined]
        yield self.do_test_command('unmute')
        self.assertFalse(self.contact.channel.muted)
        self.assertIn("No one had told me to be quiet", self.sent[0])

    @defer.inlineCallbacks
    def test_command_notify(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: [self.USER]  # type: ignore[attr-defined]
        self.assertNotIn('success', self.contact.channel.notify_events)
        yield self.do_test_command('notify', 'on success')
        self.assertIn('success', self.contact.channel.notify_events)

    @defer.inlineCallbacks
    def test_command_notify_unauthorized(self) -> InlineCallbacksType[None]:
        self.bot.getChannelOps = lambda channel: []  # type: ignore[attr-defined]
        self.assertNotIn('success', self.contact.channel.notify_events)
        yield self.do_test_command('notify', 'on success')
        self.assertNotIn('success', self.contact.channel.notify_events)

    @defer.inlineCallbacks
    def test_command_destroy(self) -> InlineCallbacksType[None]:
        self.patch_act()
        yield self.do_test_command('destroy', exp_usage=False)
        self.assertEqual(self.actions, ['readies phasers'])

    @defer.inlineCallbacks
    def test_command_dance(self) -> InlineCallbacksType[None]:
        yield self.do_test_command('dance', clock_ticks=[1.0] * 10, exp_usage=False)
        self.assertTrue(self.sent)  # doesn't matter what it sent

    @defer.inlineCallbacks
    def test_command_hustle(self) -> InlineCallbacksType[None]:
        self.patch_act()
        yield self.do_test_command('hustle', clock_ticks=[1.0] * 2, exp_usage=False)
        self.assertEqual(self.actions, ['does the hustle'])

    def test_send(self) -> None:
        events = []

        def groupChat(dest: str, msg: str) -> None:
            events.append((dest, msg))

        self.contact.bot.groupSend = groupChat

        self.contact.send("unmuted")
        self.contact.send("unmuted, unicode \N{SNOWMAN}")
        self.contact.channel.muted = True
        self.contact.send("muted")

        self.assertEqual(
            events,
            [
                ('#buildbot', 'unmuted'),
                ('#buildbot', 'unmuted, unicode \u2603'),
            ],
        )

    def test_handleAction_ignored(self) -> None:
        self.patch_act()
        self.contact.handleAction('waves hi')  # type: ignore[attr-defined]
        self.assertEqual(self.actions, [])

    def test_handleAction_kick(self) -> None:
        self.patch_act()
        self.contact.handleAction('kicks nick')  # type: ignore[attr-defined]
        self.assertEqual(self.actions, ['kicks back'])

    def test_handleAction_stupid(self) -> None:
        self.patch_act()
        self.contact.handleAction('stupids nick')  # type: ignore[attr-defined]
        self.assertEqual(self.actions, ['stupids me too'])

    def test_act(self) -> None:
        events = []

        def groupDescribe(dest: str, msg: str) -> None:
            events.append((dest, msg))

        self.contact.bot.groupDescribe = groupDescribe

        self.contact.act("unmuted")  # type: ignore[attr-defined]
        self.contact.act("unmuted, unicode \N{SNOWMAN}")  # type: ignore[attr-defined]
        self.contact.channel.muted = True
        self.contact.act("muted")  # type: ignore[attr-defined]

        self.assertEqual(
            events,
            [
                ('#buildbot', 'unmuted'),
                ('#buildbot', 'unmuted, unicode \u2603'),
            ],
        )


class FakeContact(service.AsyncService):
    def __init__(self, user: str, channel: str | None = None) -> None:
        super().__init__()
        self.user_id = user
        self.channel = mock.Mock()
        self.messages = []  # type: ignore[var-annotated]
        self.actions = []  # type: ignore[var-annotated]

    def handleMessage(self, message: str) -> None:
        self.messages.append(message)

    def handleAction(self, data: str) -> None:
        self.actions.append(data)


class TestIrcStatusBot(unittest.TestCase):
    def makeBot(self, *args: Any, **kwargs: Any) -> IrcStatusBot:
        if not args:
            args = ('nick', 'pass', ['#ch'], [], False)
        bot = irc.IrcStatusBot(*args, **kwargs)
        bot.parent = mock.Mock()
        bot.parent.master.db.state.getState = lambda *args, **kwargs: None
        return bot

    def test_groupDescribe(self) -> None:
        b = self.makeBot()
        b.describe = lambda d, m: events.append(('n', d, m))  # type: ignore[method-assign]

        events: list[tuple[str, str, str]] = []
        b.groupDescribe('#chan', 'hi')
        self.assertEqual(events, [('n', '#chan', 'hi')])

    def test_groupChat(self) -> None:
        b = self.makeBot()
        b.msg = lambda d, m: events.append(('n', d, m))  # type: ignore[method-assign, assignment, misc]

        events: list[tuple[str, str, str]] = []
        b.groupSend('#chan', 'hi')
        self.assertEqual(events, [('n', '#chan', 'hi')])

    def test_groupChat_notice(self) -> None:
        b = self.makeBot('nick', 'pass', ['#ch'], [], True)
        b.notice = lambda d, m: events.append(('n', d, m))  # type: ignore[method-assign, assignment, misc]

        events: list[tuple[str, str, str]] = []
        b.groupSend('#chan', 'hi')
        self.assertEqual(events, [('n', '#chan', 'hi')])

    def test_msg(self) -> None:
        b = self.makeBot()
        b.msg = lambda d, m: events.append(('m', d, m))  # type: ignore[method-assign, assignment, misc]

        events: list[tuple[str, str, str]] = []
        b.msg('nick', 'hi')
        self.assertEqual(events, [('m', 'nick', 'hi')])

    def test_getContact(self) -> None:
        b = self.makeBot()

        c1 = b.getContact(user='u1', channel='c1')
        c2 = b.getContact(user='u1', channel='c2')
        c1b = b.getContact(user='u1', channel='c1')

        self.assertIdentical(c1, c1b)
        self.assertIsInstance(c2, words.Contact)

    def test_getContact_case_insensitive(self) -> None:
        b = self.makeBot()

        c1 = b.getContact(user='u1')
        c1b = b.getContact(user='U1')

        self.assertIdentical(c1, c1b)

    def test_getContact_invalid(self) -> None:
        b = self.makeBot()
        b.authz = {'': None}

        u = b.getContact(user='u0', channel='c0')
        self.assertNotIn(('c0', 'u0'), b.contacts)
        self.assertNotIn('c0', b.channels)

        if platform.python_implementation() != 'PyPy':
            py_ver_str = platform.python_version_tuple()[:2]
            py_ver = (int(py_ver_str[0]), int(py_ver_str[1]))
            ref_counts = (2, 3, 2) if py_ver <= (3, 13) else (1, 2, 1)
            self.assertEqual(sys.getrefcount(u), ref_counts[0])  # local, sys
            c = u.channel
            self.assertEqual(sys.getrefcount(c), ref_counts[1])  # local, contact, sys
            del u
            self.assertEqual(sys.getrefcount(c), ref_counts[2])  # local, sys

    def test_getContact_valid(self) -> None:
        b = self.makeBot()
        b.authz = {'': None, 'command': ['u0']}

        b.getContact(user='u0', channel='c0')
        self.assertIn(('c0', 'u0'), b.contacts)

    def test_privmsg_user(self) -> None:
        b = self.makeBot()
        b.contactClass = FakeContact  # type: ignore[assignment]
        b.privmsg('jimmy!~foo@bar', 'nick', 'hello')

        c = b.getContact('jimmy')
        self.assertEqual(c.messages, ['hello'])

    def test_privmsg_user_uppercase(self) -> None:
        b = self.makeBot('NICK', 'pass', ['#ch'], [], False)
        b.contactClass = FakeContact  # type: ignore[assignment]
        b.privmsg('jimmy!~foo@bar', 'NICK', 'hello')

        c = b.getContact('jimmy')
        self.assertEqual(c.messages, ['hello'])

    def test_privmsg_channel_unrelated(self) -> None:
        b = self.makeBot()
        b.contactClass = FakeContact  # type: ignore[assignment]
        b.privmsg('jimmy!~foo@bar', '#ch', 'hello')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.messages, [])

    def test_privmsg_channel_related(self) -> None:
        b = self.makeBot()
        b.contactClass = FakeContact  # type: ignore[assignment]
        b.privmsg('jimmy!~foo@bar', '#ch', 'nick: hello')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.messages, [' hello'])

    def test_action_unrelated(self) -> None:
        b = self.makeBot()
        b.contactClass = FakeContact  # type: ignore[assignment]
        b.action('jimmy!~foo@bar', '#ch', 'waves')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.actions, [])

    def test_action_unrelated_buildbot(self) -> None:
        b = self.makeBot()
        b.contactClass = FakeContact  # type: ignore[assignment]
        # b.nickname is not 'buildbot'
        b.action('jimmy!~foo@bar', '#ch', 'waves at buildbot')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.actions, [])

    def test_action_related(self) -> None:
        b = self.makeBot()
        b.contactClass = FakeContact  # type: ignore[assignment]
        b.action('jimmy!~foo@bar', '#ch', 'waves at nick')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.actions, ['waves at nick'])

    def test_signedOn(self) -> None:
        b = self.makeBot(
            'nick',
            'pass',
            ['#ch1', {"channel": '#ch2', "password": 'sekrits'}],
            ['jimmy', 'bobby'],
            False,
        )
        events = []

        def msg(d: str, m: str) -> None:
            events.append(('m', d, m))

        b.msg = msg  # type: ignore[method-assign, assignment]

        def join(channel: str, key: str | None) -> None:
            events.append(('k', channel, key))  # type: ignore[arg-type]

        b.join = join  # type: ignore[method-assign, assignment]
        b.contactClass = FakeContact  # type: ignore[assignment]

        b.signedOn()

        self.assertEqual(
            sorted(events),
            [
                ('k', '#ch1', None),
                ('k', '#ch2', 'sekrits'),
                ('m', 'Nickserv', 'IDENTIFY pass'),
            ],
        )
        self.assertEqual(
            sorted(b.contacts.keys()),
            # channels don't get added until joined() is called
            sorted([('jimmy', 'jimmy'), ('bobby', 'bobby')]),
        )

    def test_register_SASL(self) -> None:
        b = self.makeBot('nick', 'pass', ['#ch1'], ['jimmy'], False, useSASL=True)
        events = []

        def sendLine(line: str) -> None:
            events.append(('l', line))
            if line == "AUTHENTICATE PLAIN":
                events.append(('s', "AUTHENTICATE"))
                b.irc_AUTHENTICATE(None, None)  # type: ignore[arg-type]

        b.sendLine = sendLine  # type: ignore[method-assign]

        b.register("bot")
        self.assertEqual(
            events,
            [
                ('l', 'CAP REQ :sasl'),
                ('l', 'NICK bot'),
                ('l', 'USER bot foo bar :None'),
                ('l', 'AUTHENTICATE PLAIN'),
                ('s', 'AUTHENTICATE'),
                ('l', 'AUTHENTICATE bmljawBuaWNrAHBhc3M='),
                ('l', 'CAP END'),
            ],
        )

    def test_register_legacy(self) -> None:
        b = self.makeBot('nick', 'pass', ['#ch1'], ['jimmy'], False, useSASL=False)
        events = []

        def sendLine(line: str) -> None:
            events.append(('l', line))

        b.sendLine = sendLine  # type: ignore[method-assign]

        b.register("bot")
        self.assertEqual(
            events, [('l', 'PASS pass'), ('l', 'NICK bot'), ('l', 'USER bot foo bar :None')]
        )

    def test_joined(self) -> None:
        b = self.makeBot()
        b.joined('#ch1')
        b.joined('#ch2')
        self.assertEqual(sorted(b.channels.keys()), sorted(['#ch1', '#ch2']))

    def test_userLeft_or_userKicked(self) -> None:
        b = self.makeBot()
        b.getContact(channel='c', user='u')
        self.assertIn(('c', 'u'), b.contacts)
        b.userKicked('u', 'c', 'k', 'm')
        self.assertNotIn(('c', 'u'), b.contacts)

    def test_userQuit(self) -> None:
        b = self.makeBot()
        b.getContact(channel='c1', user='u')
        b.getContact(channel='c2', user='u')
        b.getContact(user='u')
        self.assertEqual(len(b.contacts), 3)
        b.userQuit('u', 'm')
        self.assertEqual(len(b.contacts), 0)

    def test_other(self) -> None:
        # these methods just log, but let's get them covered anyway
        b = self.makeBot()
        b.left('#ch1')
        b.kickedFrom('#ch1', 'dustin', 'go away!')

    def test_format_build_status(self) -> None:
        b = self.makeBot()
        self.assertEqual(b.format_build_status({'results': SUCCESS}), "completed successfully")

    def test_format_build_status_short(self) -> None:
        b = self.makeBot()
        self.assertEqual(b.format_build_status({'results': SUCCESS}, True), ", Success")

    def test_format_build_status_colors(self) -> None:
        b = self.makeBot()
        b.useColors = True
        self.assertEqual(
            b.format_build_status({'results': SUCCESS}), "\x033completed successfully\x0f"
        )
        colors_used = set()
        status_texts = set()
        for result in ALL_RESULTS:
            status = b.format_build_status({'results': result})
            self.assertTrue(status.startswith('\x03'))
            self.assertTrue(status.endswith('\x0f'))
            i = 0
            for i, c in enumerate(status[1:-1], start=2):
                if c.isnumeric():
                    continue
                break
            colors_used.add(status[1:i])
            status_texts.add(status[i:-1])
        self.assertEqual(len(colors_used), len(ALL_RESULTS))
        self.assertEqual(len(status_texts), len(ALL_RESULTS))

    def test_getNames(self) -> None:
        b = self.makeBot()
        b.sendLine = lambda *args: None  # type: ignore[method-assign]
        d = b.getNames('#channel')
        names = []

        def cb(n: list[str]) -> None:
            names.extend(n)

        d.addCallback(cb)

        b.irc_RPL_NAMREPLY('', ('test', '=', '#channel', 'user1 user2'))  # type: ignore[arg-type]
        b.irc_RPL_ENDOFNAMES('', ('test', '#channel'))  # type: ignore[arg-type]
        self.assertEqual(names, ['user1', 'user2'])

    def test_getChannelOps(self) -> None:
        b = self.makeBot()
        b.sendLine = lambda *args: None  # type: ignore[method-assign]
        d = b.getChannelOps('#channel')
        names = []

        def cb(n: list[str]) -> None:
            names.extend(n)

        d.addCallback(cb)

        b.irc_RPL_NAMREPLY('', ('test', '=', '#channel', 'user1 @user2'))  # type: ignore[arg-type]
        b.irc_RPL_ENDOFNAMES('', ('test', '#channel'))  # type: ignore[arg-type]
        self.assertEqual(names, ['user2'])


class TestIrcStatusFactory(unittest.TestCase):
    def makeFactory(self, *args: Any, **kwargs: Any) -> IrcStatusFactory:
        if not args:
            args = ('nick', 'pass', ['ch'], [], [], {}, {})
        return irc.IrcStatusFactory(*args, **kwargs)

    def test_shutdown(self) -> None:
        # this is kinda lame, but the factory would be better tested
        # in an integration-test environment
        f = self.makeFactory()
        self.assertFalse(f.shuttingDown)
        f.shutdown()
        self.assertTrue(f.shuttingDown)


class TestIRC(config.ConfigErrorsMixin, unittest.TestCase):
    def makeIRC(self, **kwargs: Any) -> irc.IRC:
        kwargs.setdefault('host', 'localhost')
        kwargs.setdefault('nick', 'russo')
        kwargs.setdefault('channels', ['#buildbot'])
        self.factory = None

        def TCPClient(host: str, port: int, factory: IrcStatusFactory) -> mock.Mock:
            client = mock.Mock(name='tcp-client')
            client.host = host
            client.port = port
            client.factory = factory
            # keep for later
            self.factory = factory
            self.client = client
            return client

        self.patch(internet, 'TCPClient', TCPClient)
        return irc.IRC(**kwargs)

    @defer.inlineCallbacks
    def test_constr(self) -> InlineCallbacksType[None]:
        ircStatus = self.makeIRC(host='foo', port=123)
        yield ircStatus.startService()

        self.client.setServiceParent.assert_called_with(ircStatus)
        self.assertEqual(self.client.host, 'foo')
        self.assertEqual(self.client.port, 123)
        self.assertIsInstance(self.client.factory, irc.IrcStatusFactory)

    @defer.inlineCallbacks
    def test_constr_args(self) -> InlineCallbacksType[None]:
        # test that the args to IRC(..) make it all the way down to
        # the IrcStatusBot class
        s = self.makeIRC(
            host='host',
            nick='nick',
            channels=['channels'],
            pm_to_nicks=['pm', 'to', 'nicks'],
            noticeOnChannel=True,
            port=1234,
            tags=['tags'],
            password=Interpolate('pass'),
            notify_events={
                'successToFailure': 1,
            },
            showBlameList=False,
            useRevisions=True,
            useSSL=False,
            useSASL=False,
            lostDelay=10,
            failedDelay=20,
            useColors=False,
        )
        yield s.startService()

        # patch it up
        factory = self.factory
        proto_obj = mock.Mock(name='proto_obj')
        factory.protocol = mock.Mock(name='protocol', return_value=proto_obj)  # type: ignore[union-attr]

        # run it
        p = factory.buildProtocol('address')  # type: ignore[union-attr]
        self.assertIdentical(p, proto_obj)
        factory.protocol.assert_called_with(  # type: ignore[union-attr]
            'nick',
            'pass',
            ['channels'],
            ['pm', 'to', 'nicks'],
            True,
            {},
            ['tags'],
            {'successToFailure': 1},
            useColors=False,
            useSASL=False,
            useRevisions=True,
            showBlameList=False,
        )

    def test_service(self) -> defer.Deferred[None]:
        irc = self.makeIRC()
        # just put it through its paces
        irc.startService()
        return irc.stopService()

    # deprecated
    @defer.inlineCallbacks
    def test_allowForce_allowShutdown(self) -> InlineCallbacksType[None]:
        s = self.makeIRC(
            host='host', nick='nick', channels=['channels'], allowForce=True, allowShutdown=False
        )
        yield s.startService()
        self.assertEqual(
            words.StatusBot.expand_authz(s.authz), {'FORCE': True, 'STOP': True, 'SHUTDOWN': False}
        )

    # deprecated
    def test_allowForce_with_authz(self) -> None:
        with self.assertRaises(ConfigErrors):
            self.makeIRC(
                host='host',
                nick='nick',
                channels=['channels'],
                allowForce=True,
                authz={'force': [12345]},
            )

    # deprecated
    def test_allowShutdown_with_authz(self) -> None:
        with self.assertRaises(ConfigErrors):
            self.makeIRC(
                host='host',
                nick='nick',
                channels=['channels'],
                allowForce=True,
                authz={'': [12345]},
            )
