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

import mock

from twisted.application import internet
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.reporters import irc
from buildbot.reporters import words
from buildbot.test.util import config
from buildbot.util import service


class FakeContact(service.AsyncService):

    def __init__(self, bot, user=None, channel=None):
        service.AsyncService.__init__(self)
        self.bot = bot
        self.user = user
        self.channel = channel
        self.messages = []
        self.actions = []

    def handleMessage(self, message):
        self.messages.append(message)

    def handleAction(self, data):
        self.actions.append(data)


class TestIrcStatusBot(unittest.TestCase):

    def makeBot(self, *args, **kwargs):
        if not args:
            args = ('nick', 'pass', ['#ch'], [], [], {})
        return irc.IrcStatusBot(*args, **kwargs)

    def test_groupChat(self):
        b = self.makeBot()
        b.notice = lambda d, m: evts.append(('n', d, m))

        evts = []
        b.groupChat('#chan', 'hi')
        self.assertEqual(evts, [('n', '#chan', b'hi')])

    def test_chat(self):
        b = self.makeBot()
        b.msg = lambda d, m: evts.append(('m', d, m))

        evts = []
        b.chat('nick', 'hi')
        self.assertEqual(evts, [('m', 'nick', b'hi')])

    def test_getContact(self):
        b = self.makeBot()

        c1 = b.getContact(channel='c1')
        c2 = b.getContact(channel='c2')
        c1b = b.getContact(channel='c1')

        self.assertIdentical(c1, c1b)
        self.assertIsInstance(c2, words.Contact)

    def test_getContact_case_insensitive(self):
        b = self.makeBot()

        c1 = b.getContact(user='u1')
        c1b = b.getContact(user='U1')

        self.assertIdentical(c1, c1b)

    def test_privmsg_user(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', 'nick', 'hello')

        c = b.getContact('jimmy')
        self.assertEqual(c.messages, ['hello'])

    def test_privmsg_user_uppercase(self):
        b = self.makeBot('NICK', 'pass', ['#ch'], [], [], {})
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
                         ['jimmy', 'bobby'], [], {})
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
                         sorted([(None, 'jimmy'), (None, 'bobby')]))

    def test_joined(self):
        b = self.makeBot()
        b.joined('#ch1')
        b.joined('#ch2')
        self.assertEqual(sorted(b.contacts.keys()),
                         sorted([('#ch1', None), ('#ch2', None)]))

    def test_other(self):
        # these methods just log, but let's get them covered anyway
        b = self.makeBot()
        b.left('#ch1')
        b.kickedFrom('#ch1', 'dustin', 'go away!')


class TestIrcStatusFactory(unittest.TestCase):

    def makeFactory(self, *args, **kwargs):
        if not args:
            args = ('nick', 'pass', ['ch'], [], [], {})
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
            port=1234,
            allowForce=True,
            tags=['tags'],
            password='pass',
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
            'nick', 'pass', ['channels'], ['pm', 'to', 'nicks'],
            ['tags'], {'successToFailure': 1},
            useColors=False,
            useRevisions=True,
            showBlameList=False)

    def test_allowForce_notBool(self):
        """
        When L{IRCClient} is called with C{allowForce} not a boolean,
        a config error is reported.
        """
        self.assertRaisesConfigError("allowForce must be boolean, not",
                                     lambda: self.makeIRC(allowForce=object()))

    def test_allowShutdown_notBool(self):
        """
        When L{IRCClient} is called with C{allowShutdown} not a boolean,
        a config error is reported.
        """
        self.assertRaisesConfigError("allowShutdown must be boolean, not",
                                     lambda: self.makeIRC(allowShutdown=object()))

    def test_service(self):
        irc = self.makeIRC()
        # just put it through its paces
        irc.startService()
        return irc.stopService()
