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


import sys

import mock

from twisted.application import internet
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import ConfigErrors
from buildbot.process.properties import Interpolate
from buildbot.process.results import ALL_RESULTS
from buildbot.process.results import SUCCESS
from buildbot.reporters import irc
from buildbot.reporters import words
from buildbot.test.unit.test_reporters_words import ContactMixin
from buildbot.test.util import config
from buildbot.util import service


class TestIrcContact(ContactMixin, unittest.TestCase):
    channelClass = irc.IRCChannel
    contactClass = irc.IRCContact

    def patch_act(self):
        self.actions = []

        def act(msg):
            self.actions.append(msg)
        self.contact.act = act

    @defer.inlineCallbacks
    def test_op_required_authz(self):
        self.bot.authz = self.bot.expand_authz({
            ('mute', 'unmute'): [self.USER]
        })
        self.bot.getChannelOps = lambda channel: ['channelop']
        self.assertFalse((yield self.contact.op_required('mute')))

    @defer.inlineCallbacks
    def test_op_required_operator(self):
        self.bot.getChannelOps = lambda channel: [self.USER]
        self.assertFalse((yield self.contact.op_required('command')))

    @defer.inlineCallbacks
    def test_op_required_unauthorized(self):
        self.bot.getChannelOps = lambda channel: ['channelop']
        self.assertTrue((yield self.contact.op_required('command')))

    @defer.inlineCallbacks
    def test_command_mute(self):
        self.bot.getChannelOps = lambda channel: [self.USER]
        yield self.do_test_command('mute')
        self.assertTrue(self.contact.channel.muted)

    @defer.inlineCallbacks
    def test_command_mute_unauthorized(self):
        self.bot.getChannelOps = lambda channel: []
        yield self.do_test_command('mute')
        self.assertFalse(self.contact.channel.muted)
        self.assertIn("blah, blah", self.sent[0])

    @defer.inlineCallbacks
    def test_command_unmute(self):
        self.bot.getChannelOps = lambda channel: [self.USER]
        self.contact.channel.muted = True
        yield self.do_test_command('unmute')
        self.assertFalse(self.contact.channel.muted)

    @defer.inlineCallbacks
    def test_command_unmute_unauthorized(self):
        self.bot.getChannelOps = lambda channel: []
        self.contact.channel.muted = True
        yield self.do_test_command('unmute')
        self.assertTrue(self.contact.channel.muted)

    @defer.inlineCallbacks
    def test_command_unmute_not_muted(self):
        self.bot.getChannelOps = lambda channel: [self.USER]
        yield self.do_test_command('unmute')
        self.assertFalse(self.contact.channel.muted)
        self.assertIn("No one had told me to be quiet", self.sent[0])

    @defer.inlineCallbacks
    def test_command_notify(self):
        self.bot.getChannelOps = lambda channel: [self.USER]
        self.assertNotIn('success', self.contact.channel.notify_events)
        yield self.do_test_command('notify', 'on success')
        self.assertIn('success', self.contact.channel.notify_events)

    @defer.inlineCallbacks
    def test_command_notify_unauthorized(self):
        self.bot.getChannelOps = lambda channel: []
        self.assertNotIn('success', self.contact.channel.notify_events)
        yield self.do_test_command('notify', 'on success')
        self.assertNotIn('success', self.contact.channel.notify_events)

    @defer.inlineCallbacks
    def test_command_destroy(self):
        self.patch_act()
        yield self.do_test_command('destroy', exp_usage=False)
        self.assertEqual(self.actions, ['readies phasers'])

    @defer.inlineCallbacks
    def test_command_dance(self):
        yield self.do_test_command('dance', clock_ticks=[1.0] * 10, exp_usage=False)
        self.assertTrue(self.sent)  # doesn't matter what it sent

    @defer.inlineCallbacks
    def test_command_hustle(self):
        self.patch_act()
        yield self.do_test_command('hustle', clock_ticks=[1.0] * 2, exp_usage=False)
        self.assertEqual(self.actions, ['does the hustle'])

    def test_send(self):
        events = []

        def groupChat(dest, msg):
            events.append((dest, msg))
        self.contact.bot.groupSend = groupChat

        self.contact.send("unmuted")
        self.contact.send("unmuted, unicode \N{SNOWMAN}")
        self.contact.channel.muted = True
        self.contact.send("muted")

        self.assertEqual(events, [
            ('#buildbot', 'unmuted'),
            ('#buildbot', 'unmuted, unicode \u2603'),
        ])

    def test_handleAction_ignored(self):
        self.patch_act()
        self.contact.handleAction('waves hi')
        self.assertEqual(self.actions, [])

    def test_handleAction_kick(self):
        self.patch_act()
        self.contact.handleAction('kicks nick')
        self.assertEqual(self.actions, ['kicks back'])

    def test_handleAction_stupid(self):
        self.patch_act()
        self.contact.handleAction('stupids nick')
        self.assertEqual(self.actions, ['stupids me too'])

    def test_act(self):
        events = []

        def groupDescribe(dest, msg):
            events.append((dest, msg))
        self.contact.bot.groupDescribe = groupDescribe

        self.contact.act("unmuted")
        self.contact.act("unmuted, unicode \N{SNOWMAN}")
        self.contact.channel.muted = True
        self.contact.act("muted")

        self.assertEqual(events, [
            ('#buildbot', 'unmuted'),
            ('#buildbot', 'unmuted, unicode \u2603'),
        ])


class FakeContact(service.AsyncService):

    def __init__(self, user, channel=None):
        super().__init__()
        self.user_id = user
        self.channel = mock.Mock()
        self.messages = []
        self.actions = []

    def handleMessage(self, message):
        self.messages.append(message)

    def handleAction(self, data):
        self.actions.append(data)


class TestIrcStatusBot(unittest.TestCase):

    def makeBot(self, *args, **kwargs):
        if not args:
            args = ('nick', 'pass', ['#ch'], [], False)
        bot = irc.IrcStatusBot(*args, **kwargs)
        bot.parent = mock.Mock()
        bot.parent.master.db.state.getState = lambda *args, **kwargs: None
        return bot

    def test_groupDescribe(self):
        b = self.makeBot()
        b.describe = lambda d, m: evts.append(('n', d, m))

        evts = []
        b.groupDescribe('#chan', 'hi')
        self.assertEqual(evts, [('n', '#chan', 'hi')])

    def test_groupChat(self):
        b = self.makeBot()
        b.msg = lambda d, m: evts.append(('n', d, m))

        evts = []
        b.groupSend('#chan', 'hi')
        self.assertEqual(evts, [('n', '#chan', 'hi')])

    def test_groupChat_notice(self):
        b = self.makeBot('nick', 'pass', ['#ch'], [], True)
        b.notice = lambda d, m: evts.append(('n', d, m))

        evts = []
        b.groupSend('#chan', 'hi')
        self.assertEqual(evts, [('n', '#chan', 'hi')])

    def test_msg(self):
        b = self.makeBot()
        b.msg = lambda d, m: evts.append(('m', d, m))

        evts = []
        b.msg('nick', 'hi')
        self.assertEqual(evts, [('m', 'nick', 'hi')])

    def test_getContact(self):
        b = self.makeBot()

        c1 = b.getContact(user='u1', channel='c1')
        c2 = b.getContact(user='u1', channel='c2')
        c1b = b.getContact(user='u1', channel='c1')

        self.assertIdentical(c1, c1b)
        self.assertIsInstance(c2, words.Contact)

    def test_getContact_case_insensitive(self):
        b = self.makeBot()

        c1 = b.getContact(user='u1')
        c1b = b.getContact(user='U1')

        self.assertIdentical(c1, c1b)

    def test_getContact_invalid(self):
        b = self.makeBot()
        b.authz = {'': None}

        u = b.getContact(user='u0', channel='c0')
        self.assertNotIn(('c0', 'u0'), b.contacts)
        self.assertNotIn('c0', b.channels)

        self.assertEqual(sys.getrefcount(u), 2)  # local, sys
        c = u.channel
        self.assertEqual(sys.getrefcount(c), 3)  # local, contact, sys
        del u
        self.assertEqual(sys.getrefcount(c), 2)  # local, sys

    def test_getContact_valid(self):
        b = self.makeBot()
        b.authz = {'': None, 'command': ['u0']}

        b.getContact(user='u0', channel='c0')
        self.assertIn(('c0', 'u0'), b.contacts)

    def test_privmsg_user(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', 'nick', 'hello')

        c = b.getContact('jimmy')
        self.assertEqual(c.messages, ['hello'])

    def test_privmsg_user_uppercase(self):
        b = self.makeBot('NICK', 'pass', ['#ch'], [], False)
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', 'NICK', 'hello')

        c = b.getContact('jimmy')
        self.assertEqual(c.messages, ['hello'])

    def test_privmsg_channel_unrelated(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', '#ch', 'hello')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.messages, [])

    def test_privmsg_channel_related(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', '#ch', 'nick: hello')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.messages, [' hello'])

    def test_action_unrelated(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.action('jimmy!~foo@bar', '#ch', 'waves')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.actions, [])

    def test_action_unrelated_buildbot(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        # b.nickname is not 'buildbot'
        b.action('jimmy!~foo@bar', '#ch', 'waves at buildbot')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.actions, [])

    def test_action_related(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.action('jimmy!~foo@bar', '#ch', 'waves at nick')

        c = b.getContact('jimmy', '#ch')
        self.assertEqual(c.actions, ['waves at nick'])

    def test_signedOn(self):
        b = self.makeBot('nick', 'pass',
                         ['#ch1', dict(channel='#ch2', password='sekrits')],
                         ['jimmy', 'bobby'], False)
        evts = []

        def msg(d, m):
            evts.append(('m', d, m))
        b.msg = msg

        def join(channel, key):
            evts.append(('k', channel, key))
        b.join = join
        b.contactClass = FakeContact

        b.signedOn()

        self.assertEqual(sorted(evts), [
            ('k', '#ch1', None),
            ('k', '#ch2', 'sekrits'),
            ('m', 'Nickserv', 'IDENTIFY pass'),
        ])
        self.assertEqual(sorted(b.contacts.keys()),
                         # channels don't get added until joined() is called
                         sorted([('jimmy', 'jimmy'), ('bobby', 'bobby')]))

    def test_joined(self):
        b = self.makeBot()
        b.joined('#ch1')
        b.joined('#ch2')
        self.assertEqual(sorted(b.channels.keys()),
                         sorted(['#ch1', '#ch2']))

    def test_userLeft_or_userKicked(self):
        b = self.makeBot()
        b.getContact(channel='c', user='u')
        self.assertIn(('c', 'u'), b.contacts)
        b.userKicked('u', 'c', 'k', 'm')
        self.assertNotIn(('c', 'u'), b.contacts)

    def test_userQuit(self):
        b = self.makeBot()
        b.getContact(channel='c1', user='u')
        b.getContact(channel='c2', user='u')
        b.getContact(user='u')
        self.assertEquals(len(b.contacts), 3)
        b.userQuit('u', 'm')
        self.assertEquals(len(b.contacts), 0)

    def test_other(self):
        # these methods just log, but let's get them covered anyway
        b = self.makeBot()
        b.left('#ch1')
        b.kickedFrom('#ch1', 'dustin', 'go away!')

    def test_format_build_status(self):
        b = self.makeBot()
        self.assertEquals(b.format_build_status({'results': SUCCESS}),
                          "completed successfully")

    def test_format_build_status_short(self):
        b = self.makeBot()
        self.assertEquals(b.format_build_status({'results': SUCCESS}, True),
                          ", Success")

    def test_format_build_status_colors(self):
        b = self.makeBot()
        b.useColors = True
        self.assertEqual(b.format_build_status({'results': SUCCESS}),
                         "\x033completed successfully\x0f")
        colors_used = set()
        status_texts = set()
        for result in ALL_RESULTS:
            status = b.format_build_status({'results': result})
            self.assertTrue(status.startswith('\x03'))
            self.assertTrue(status.endswith('\x0f'))
            for i, c in enumerate(status[1:-1], start=2):
                if c.isnumeric():
                    continue
                break
            colors_used.add(status[1:i])
            status_texts.add(status[i:-1])
        self.assertEqual(len(colors_used), len(ALL_RESULTS))
        self.assertEqual(len(status_texts), len(ALL_RESULTS))

    def test_getNames(self):
        b = self.makeBot()
        b.sendLine = lambda *args: None
        d = b.getNames('#channel')
        names = []

        def cb(n):
            names.extend(n)
        d.addCallback(cb)

        b.irc_RPL_NAMREPLY('', ('test', '=', '#channel', 'user1 user2'))
        b.irc_RPL_ENDOFNAMES('', ('test', '#channel'))
        self.assertEqual(names, ['user1', 'user2'])

    def test_getChannelOps(self):
        b = self.makeBot()
        b.sendLine = lambda *args: None
        d = b.getChannelOps('#channel')
        names = []

        def cb(n):
            names.extend(n)
        d.addCallback(cb)

        b.irc_RPL_NAMREPLY('', ('test', '=', '#channel', 'user1 @user2'))
        b.irc_RPL_ENDOFNAMES('', ('test', '#channel'))
        self.assertEqual(names, ['user2'])


class TestIrcStatusFactory(unittest.TestCase):

    def makeFactory(self, *args, **kwargs):
        if not args:
            args = ('nick', 'pass', ['ch'], [], [], {}, {})
        return irc.IrcStatusFactory(*args, **kwargs)

    def test_shutdown(self):
        # this is kinda lame, but the factory would be better tested
        # in an integration-test environment
        f = self.makeFactory()
        self.assertFalse(f.shuttingDown)
        f.shutdown()
        self.assertTrue(f.shuttingDown)


class TestIRC(config.ConfigErrorsMixin, unittest.TestCase):

    def makeIRC(self, **kwargs):
        kwargs.setdefault('host', 'localhost')
        kwargs.setdefault('nick', 'russo')
        kwargs.setdefault('channels', ['#buildbot'])
        self.factory = None

        def TCPClient(host, port, factory):
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
    def test_constr(self):
        ircStatus = self.makeIRC(host='foo', port=123)
        yield ircStatus.startService()

        self.client.setServiceParent.assert_called_with(ircStatus)
        self.assertEqual(self.client.host, 'foo')
        self.assertEqual(self.client.port, 123)
        self.assertIsInstance(self.client.factory, irc.IrcStatusFactory)

    @defer.inlineCallbacks
    def test_constr_args(self):
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
            notify_events={'successToFailure': 1, },
            showBlameList=False,
            useRevisions=True,
            useSSL=False,
            lostDelay=10,
            failedDelay=20,
            useColors=False)
        yield s.startService()

        # patch it up
        factory = self.factory
        proto_obj = mock.Mock(name='proto_obj')
        factory.protocol = mock.Mock(name='protocol', return_value=proto_obj)

        # run it
        p = factory.buildProtocol('address')
        self.assertIdentical(p, proto_obj)
        factory.protocol.assert_called_with(
            'nick', 'pass', ['channels'], ['pm', 'to', 'nicks'], True,
            {}, ['tags'], {'successToFailure': 1},
            useColors=False,
            useRevisions=True,
            showBlameList=False)

    def test_service(self):
        irc = self.makeIRC()
        # just put it through its paces
        irc.startService()
        return irc.stopService()

    # deprecated
    @defer.inlineCallbacks
    def test_allowForce_allowShutdown(self):
        s = self.makeIRC(
            host='host',
            nick='nick',
            channels=['channels'],
            allowForce=True,
            allowShutdown=False)
        yield s.startService()
        self.assertEqual(words.StatusBot.expand_authz(s.authz), {'FORCE': True, 'STOP': True, 'SHUTDOWN': False})

    # deprecated
    def test_allowForce_with_authz(self):
        with self.assertRaises(ConfigErrors):
            self.makeIRC(
                host='host',
                nick='nick',
                channels=['channels'],
                allowForce=True,
                authz={'force': [12345]})

    # deprecated
    def test_allowShutdown_with_authz(self):
        with self.assertRaises(ConfigErrors):
            self.makeIRC(
                host='host',
                nick='nick',
                channels=['channels'],
                allowForce=True,
                authz={'': [12345]})
