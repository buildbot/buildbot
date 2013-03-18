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

import mock
from twisted.trial import unittest
from twisted.application import internet
from twisted.internet import task, reactor
from buildbot.status import words
from buildbot.test.util import compat

class TestIrcContactChannel(unittest.TestCase):

    def setUp(self):
        self.bot = mock.Mock(name='IRCStatusBot-instance')
        self.bot.nickname = 'nick'
        self.bot.notify_events = { 'success' : 1, 'failure' : 1 }

        # fake out subscription/unsubscription
        self.subscribed = False
        def subscribe(contact):
            self.subscribed = True
        self.bot.status.subscribe = subscribe
        def unsubscribe(contact):
            self.subscribed = False
        self.bot.status.unsubscribe = unsubscribe

        # fake out clean shutdown
        self.bot.master = mock.Mock(name='IRCStatusBot-instance.master')
        self.bot.master.botmaster = mock.Mock(name='IRCStatusBot-instance.master.botmaster')
        self.bot.master.botmaster.shuttingDown = False
        def cleanShutdown():
            self.bot.master.botmaster.shuttingDown = True
        self.bot.master.botmaster.cleanShutdown = cleanShutdown
        def cancelCleanShutdown():
            self.bot.master.botmaster.shuttingDown = False
        self.bot.master.botmaster.cancelCleanShutdown = cancelCleanShutdown

        self.contact = words.IRCContact(self.bot, '#buildbot')

    def patch_send(self):
        self.sent = []
        def send(msg):
            self.sent.append(msg)
        self.contact.send = send

    def patch_act(self):
        self.actions = []
        def act(msg):
            self.actions.append(msg)
        self.contact.act = act

    def do_test_command(self, command, args='', who='me', clock_ticks=None,
            exp_usage=True, exp_UsageError=False, allowShutdown=False,
            shuttingDown=False):
        cmd = getattr(self.contact, 'command_' + command.upper())

        if exp_usage:
            self.assertTrue(hasattr(cmd, 'usage'))

        clock = task.Clock()
        self.patch(reactor, 'callLater', clock.callLater)
        self.patch_send()
        self.patch_act()
        self.bot.factory.allowShutdown = allowShutdown
        self.bot.master.botmaster.shuttingDown = shuttingDown

        if exp_UsageError:
            try:
                cmd(args, who)
            except words.UsageError:
                return
            else:
                self.fail("no UsageError")
        else:
            cmd(args, who)
        if clock_ticks:
            clock.pump(clock_ticks)

    # tests

    def test_doSilly(self):
        clock = task.Clock()
        self.patch(reactor, 'callLater', clock.callLater)
        self.patch_send()
        silly_prompt, silly_response = self.contact.silly.items()[0]

        self.contact.doSilly(silly_prompt)
        clock.pump([0.5] * 20)

        self.assertEqual(self.sent, silly_response)

    # TODO: remaining commands
    # (all depend on status, which interface will change soon)

    def test_command_mute(self):
        self.do_test_command('mute')
        self.assertTrue(self.contact.muted)

    def test_command_unmute(self):
        self.contact.muted = True
        self.do_test_command('unmute')
        self.assertFalse(self.contact.muted)

    def test_command_unmute_not_muted(self):
        self.do_test_command('unmute')
        self.assertFalse(self.contact.muted)
        self.assertIn("hadn't told me to be quiet", self.sent[0])

    def test_command_help_noargs(self):
        self.do_test_command('help')
        self.assertIn('help on what', self.sent[0])

    def test_command_help_arg(self):
        self.contact.command_FOO = lambda : None
        self.contact.command_FOO.usage = 'foo - bar'
        self.do_test_command('help', args='foo')
        self.assertIn('Usage: foo - bar', self.sent[0])

    def test_command_help_no_usage(self):
        self.contact.command_FOO = lambda : None
        self.do_test_command('help', args='foo')
        self.assertIn('No usage info for', self.sent[0])

    def test_command_help_dict_command(self):
        self.contact.command_FOO = lambda : None
        self.contact.command_FOO.usage = {
            None : 'foo - bar'
        }
        self.do_test_command('help', args='foo')
        self.assertIn('Usage: foo - bar', self.sent[0])

    def test_command_help_dict_command_no_usage(self):
        self.contact.command_FOO = lambda : None
        self.contact.command_FOO.usage = {}
        self.do_test_command('help', args='foo')
        self.assertIn("No usage info for 'foo'", self.sent[0])

    def test_command_help_dict_command_arg(self):
        self.contact.command_FOO = lambda : None
        self.contact.command_FOO.usage = {
            'this' : 'foo this - bar'
        }
        self.do_test_command('help', args='foo this')
        self.assertIn('Usage: foo this - bar', self.sent[0])

    def test_command_help_dict_command_arg_no_usage(self):
        self.contact.command_FOO = lambda : None
        self.contact.command_FOO.usage = {
            # nothing for arg 'this'
            ('this', 'first') : 'foo this first - bar'
        }
        self.do_test_command('help', args='foo this')
        self.assertIn("No usage info for 'foo' 'this'", self.sent[0])

    def test_command_help_dict_command_arg_subarg(self):
        self.contact.command_FOO = lambda : None
        self.contact.command_FOO.usage = {
            ('this', 'first') : 'foo this first - bar'
        }
        self.do_test_command('help', args='foo this first')
        self.assertIn('Usage: foo this first - bar', self.sent[0])

    def test_command_help_dict_command_arg_subarg_no_usage(self):
        self.contact.command_FOO = lambda : None
        self.contact.command_FOO.usage = {
            None : 'foo - bar',
            'this' : 'foo this - bar',
            ('this', 'first') : 'foo this first - bar'
            # nothing for subarg 'missing'
        }
        self.do_test_command('help', args='foo this missing')
        self.assertIn("No usage info for 'foo' 'this' 'missing'", self.sent[0])

    def test_command_help_nosuch(self):
        self.do_test_command('help', args='foo', exp_UsageError=True)

    def test_command_shutdown(self):
        self.do_test_command('shutdown', exp_UsageError=True)
        self.assertEqual(self.bot.factory.allowShutdown, False)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)

    def test_command_shutdown_dissalowed(self):
        self.do_test_command('shutdown', args='check', exp_UsageError=True)
        self.assertEqual(self.bot.factory.allowShutdown, False)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)

    def test_command_shutdown_check_running(self):
        self.do_test_command('shutdown', args='check', allowShutdown=True, shuttingDown=False)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)
        self.assertIn('buildbot is running', self.sent[0])

    def test_command_shutdown_check_shutting_down(self):
        self.do_test_command('shutdown', args='check', allowShutdown=True, shuttingDown=True)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, True)
        self.assertIn('buildbot is shutting down', self.sent[0])

    def test_command_shutdown_start(self):
        self.do_test_command('shutdown', args='start', allowShutdown=True, shuttingDown=False)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, True)

    def test_command_shutdown_stop(self):
        self.do_test_command('shutdown', args='stop', allowShutdown=True, shuttingDown=True)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)

    def test_command_shutdown_now(self):
        stop = mock.Mock()
        self.patch(reactor, 'stop', stop)
        self.do_test_command('shutdown', args='now', allowShutdown=True)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)
        stop.assert_called_with()

    def test_command_source(self):
        self.do_test_command('source')
        self.assertIn('My source', self.sent[0])

    def test_command_commands(self):
        self.do_test_command('commands')
        self.assertIn('buildbot commands', self.sent[0])

    def test_command_destroy(self):
        self.do_test_command('destroy', exp_usage=False)
        self.assertEqual(self.actions, [ 'readies phasers' ])

    def test_command_dance(self):
        self.do_test_command('dance', clock_ticks=[1.0]*10, exp_usage=False)
        self.assertTrue(self.sent) # doesn't matter what it sent

    def test_send(self):
        events = []
        def msgOrNotice(dest, msg):
            events.append((dest, msg))
        self.contact.bot.msgOrNotice = msgOrNotice

        self.contact.send("unmuted")
        self.contact.send(u"unmuted, unicode \N{SNOWMAN}")
        self.contact.muted = True
        self.contact.send("muted")

        self.assertEqual(events, [
            ('#buildbot', 'unmuted'),
            ('#buildbot', 'unmuted, unicode ?'),
        ])

    def test_act(self):
        events = []
        def describe(dest, msg):
            events.append((dest, msg))
        self.contact.bot.describe = describe

        self.contact.act("unmuted")
        self.contact.act(u"unmuted, unicode \N{SNOWMAN}")
        self.contact.muted = True
        self.contact.act("muted")

        self.assertEqual(events, [
            ('#buildbot', 'unmuted'),
            ('#buildbot', 'unmuted, unicode ?'),
        ])

    def test_handleMessage_silly(self):
        silly_prompt = self.contact.silly.keys()[0]
        self.contact.doSilly = mock.Mock()
        d = self.contact.handleMessage(silly_prompt, 'me')
        @d.addCallback
        def cb(_):
            self.contact.doSilly.assert_called_with(silly_prompt)
        return d

    def test_handleMessage_short_command(self):
        self.contact.command_TESTY = mock.Mock()
        d = self.contact.handleMessage('testy', 'me')
        @d.addCallback
        def cb(_):
            self.contact.command_TESTY.assert_called_with('', 'me')
        return d

    def test_handleMessage_long_command(self):
        self.contact.command_TESTY = mock.Mock()
        d = self.contact.handleMessage('testy   westy boo', 'me')
        @d.addCallback
        def cb(_):
            self.contact.command_TESTY.assert_called_with('westy boo', 'me')
        return d

    def test_handleMessage_excited(self):
        self.patch_send()
        d = self.contact.handleMessage('hi!', 'me')
        @d.addCallback
        def cb(_):
            self.assertEqual(len(self.sent), 1) # who cares what it says..
        return d

    @compat.usesFlushLoggedErrors
    def test_handleMessage_exception(self):
        self.patch_send()
        def command_TESTY(msg, who):
            raise RuntimeError("FAIL")
        self.contact.command_TESTY = command_TESTY
        d = self.contact.handleMessage('testy boom', 'me')
        @d.addCallback
        def cb(_):
            self.assertEqual(self.sent,
                    [ "Something bad happened (see logs)" ])
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        return d

    def test_handleMessage_UsageError(self):
        self.patch_send()
        def command_TESTY(msg, who):
            raise words.UsageError("oh noes")
        self.contact.command_TESTY = command_TESTY
        d = self.contact.handleMessage('testy boom', 'me')
        @d.addCallback
        def cb(_):
            self.assertEqual(self.sent, [ "oh noes" ])
        return d

    def test_handleAction_ignored(self):
        self.patch_act()
        self.contact.handleAction('waves hi', 'me')
        self.assertEqual(self.actions, [])

    def test_handleAction_kick(self):
        self.patch_act()
        self.contact.handleAction('kicks nick', 'me')
        self.assertEqual(self.actions, ['kicks back'])

    def test_handleAction_stpuid(self):
        self.patch_act()
        self.contact.handleAction('stupids nick', 'me')
        self.assertEqual(self.actions, ['stupids me too'])

    def test_unclosed_quote(self):
        self.do_test_command('list', args='args\'', exp_UsageError=True)
        self.do_test_command('status', args='args\'', exp_UsageError=True)
        self.do_test_command('notify', args='args\'', exp_UsageError=True)
        self.do_test_command('watch', args='args\'', exp_UsageError=True)
        self.do_test_command('force', args='args\'', exp_UsageError=True)
        self.do_test_command('stop', args='args\'', exp_UsageError=True)
        self.do_test_command('last', args='args\'', exp_UsageError=True)
        self.do_test_command('help', args='args\'', exp_UsageError=True)


class FakeContact(object):

    def __init__(self, bot, name):
        self.bot = bot
        self.name = name
        self.messages = []
        self.actions = []

    def handleMessage(self, message, user):
        self.messages.append((message, user))

    def handleAction(self, data, user):
        self.actions.append((data, user))


class TestIrcStatusBot(unittest.TestCase):

    def setUp(self):
        self.status = mock.Mock(name='status')

    def makeBot(self, *args, **kwargs):
        if not args:
            args = ('nick', 'pass', ['#ch'], [], self.status, [], {})
        return words.IrcStatusBot(*args, **kwargs)

    def test_msgOrNotice(self):
        b = self.makeBot(noticeOnChannel=False)
        b.notice = lambda d, m : evts.append(('n', d, m))
        b.msg = lambda d, m : evts.append(('m', d, m))

        evts = []
        b.msgOrNotice('nick', 'hi')
        self.assertEqual(evts, [('m', 'nick', 'hi')])

        evts = []
        b.msgOrNotice('#chan', 'hi')
        self.assertEqual(evts, [('m', '#chan', 'hi')])

        b.noticeOnChannel = True

        evts = []
        b.msgOrNotice('#chan', 'hi')
        self.assertEqual(evts, [('n', '#chan', 'hi')])

    def test_getContact(self):
        b = self.makeBot()

        c1 = b.getContact('c1')
        c2 = b.getContact('c2')
        c1b = b.getContact('c1')

        self.assertIdentical(c1, c1b)
        self.assertIsInstance(c2, words.IRCContact)

    def test_getContact_case_insensitive(self):
        b = self.makeBot()

        c1 = b.getContact('c1')
        c1b = b.getContact('C1')

        self.assertIdentical(c1, c1b)

    def test_privmsg_user(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', 'nick', 'hello')

        c = b.getContact('jimmy')
        self.assertEqual(c.messages, [('hello', 'jimmy')])

    def test_privmsg_user_uppercase(self):
        b = self.makeBot('NICK', 'pass', ['#ch'], [], self.status, [], {})
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', 'NICK', 'hello')

        c = b.getContact('jimmy')
        self.assertEqual(c.messages, [('hello', 'jimmy')])

    def test_privmsg_channel_unrelated(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', '#ch', 'hello')

        c = b.getContact('#ch')
        self.assertEqual(c.messages, [])

    def test_privmsg_channel_related(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.privmsg('jimmy!~foo@bar', '#ch', 'nick: hello')

        c = b.getContact('#ch')
        self.assertEqual(c.messages, [(' hello', 'jimmy')])

    def test_action_unrelated(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.action('jimmy!~foo@bar', '#ch', 'waves')

        c = b.getContact('#ch')
        self.assertEqual(c.actions, [])

    def test_action_unrelated_buildbot(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.action('jimmy!~foo@bar', '#ch', 'waves at buildbot')# b.nickname is not 'buildbot'

        c = b.getContact('#ch')
        self.assertEqual(c.actions, [])

    def test_action_related(self):
        b = self.makeBot()
        b.contactClass = FakeContact
        b.action('jimmy!~foo@bar', '#ch', 'waves at nick')

        c = b.getContact('#ch')
        self.assertEqual(c.actions, [('waves at nick', 'jimmy')])

    def test_signedOn(self):
        b = self.makeBot('nick', 'pass',
                ['#ch1', dict(channel='#ch2', password='sekrits')],
                ['jimmy', 'bobby'], self.status, [], {})
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
                sorted(['jimmy', 'bobby']))

    def test_joined(self):
        b = self.makeBot()
        b.joined('#ch1')
        b.joined('#ch2')
        self.assertEqual(sorted(b.contacts.keys()),
                sorted(['#ch1', '#ch2']))

    def test_other(self):
        # these methods just log, but let's get them covered anyway
        b = self.makeBot()
        b.left('#ch1')
        b.kickedFrom('#ch1', 'dustin', 'go away!')


class TestIrcStatusFactory(unittest.TestCase):

    def makeFactory(self, *args, **kwargs):
        if not args:
            args = ('nick', 'pass', ['ch'], [], [], {})
        return words.IrcStatusFactory(*args, **kwargs)

    def test_shutdown(self):
        # this is kinda lame, but the factory would be better tested
        # in an integration-test environment
        f = self.makeFactory()
        self.assertFalse(f.shuttingDown)
        f.shutdown()
        self.assertTrue(f.shuttingDown)


class TestIRC(unittest.TestCase):

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
        return words.IRC(**kwargs)

    def test_constr(self):
        irc = self.makeIRC(host='foo', port=123)
        self.client.setServiceParent.assert_called_with(irc)
        self.assertEqual(self.client.host, 'foo')
        self.assertEqual(self.client.port, 123)
        self.assertIsInstance(self.client.factory, words.IrcStatusFactory)

    def test_constr_args(self):
        # test that the args to IRC(..) make it all the way down to
        # the IrcStatusBot class
        self.makeIRC(
            host='host',
            nick='nick',
            channels=['channels'],
            pm_to_nicks=['pm', 'to', 'nicks'],
            port=1234,
            allowForce=True,
            categories=['categories'],
            password='pass',
            notify_events={ 'successToFailure': 1, },
            noticeOnChannel=True,
            showBlameList=False,
            useRevisions=True,
            useSSL=False,
            lostDelay=10,
            failedDelay=20,
            useColors=False)

        # patch it up
        factory = self.factory
        proto_obj = mock.Mock(name='proto_obj')
        factory.protocol = mock.Mock(name='protocol', return_value=proto_obj)
        factory.status = 'STATUS'

        # run it
        p = factory.buildProtocol('address')
        self.assertIdentical(p, proto_obj)
        factory.protocol.assert_called_with(
                'nick', 'pass', ['channels'], ['pm', 'to', 'nicks'],
                factory.status, ['categories'], { 'successToFailure': 1 },
                noticeOnChannel=True,
                useColors=False,
                useRevisions=True,
                showBlameList=False)

    def test_service(self):
        irc = self.makeIRC()
        # just put it through its paces
        irc.startService()
        return irc.stopService()
