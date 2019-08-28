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

import types

from twisted.application import internet
from twisted.internet import task
from twisted.python import log
from twisted.words.protocols import irc

from buildbot import config
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters.words import Channel
from buildbot.reporters.words import Contact
from buildbot.reporters.words import StatusBot
from buildbot.reporters.words import ThrottledClientFactory
from buildbot.util import service
from buildbot.util import ssl


class UsageError(ValueError):

    # pylint: disable=useless-super-delegation
    def __init__(self, string="Invalid usage", *more):
        # This is not useless as we change the default value of an argument.
        # This bug is reported as "fixed" but apparently, it is not.
        # https://github.com/PyCQA/pylint/issues/1085
        # (Maybe there is a problem with builtin exceptions).
        super().__init__(string, *more)


_irc_colors = (
    'WHITE',
    'BLACK',
    'NAVY_BLUE',
    'GREEN',
    'RED',
    'BROWN',
    'PURPLE',
    'OLIVE',
    'YELLOW',
    'LIME_GREEN',
    'TEAL',
    'AQUA_LIGHT',
    'ROYAL_BLUE',
    'HOT_PINK',
    'DARK_GRAY',
    'LIGHT_GRAY'
)


class IRCChannel(Channel):

    def __init__(self, bot, channel):
        super().__init__(bot, channel)
        self.muted = False

    def send(self, message):
        if self.id[0] in irc.CHANNEL_PREFIXES:
            send = self.bot.groupSend
        else:
            send = self.bot.msg
        if self.muted:
            return
        if isinstance(message, (list, tuple, types.GeneratorType)):
            for m in message:
                send(self.id, m)
        else:
            send(self.id, message)

    def act(self, action):
        if self.muted:
            return
        self.bot.groupDescribe(self.id, action)


class IRCContact(Contact):

    def __init__(self, bot, user=None, channel=None):
        super().__init__(bot, user, channel)

    def send(self, message):
        return self.channel.send(message)

    def act(self, action):
        return self.channel.act(action)

    def handleAction(self, action):
        # this is sent when somebody performs an action that mentions the
        # buildbot (like '/me kicks buildbot'). 'self.user' is the name/nick/id of
        # the person who performed the action, so if their action provokes a
        # response, they can be named.  This is 100% silly.
        if not action.endswith("s " + self.bot.nickname):
            return
        words = action.split()
        verb = words[-2]
        if verb == "kicks":
            response = "%s back" % verb
        elif verb == "threatens":
            response = "hosts a red wedding for %s" % self.user
        else:
            response = "%s %s too" % (verb, self.user)
        self.act(response)

    # IRC only commands

    def command_MUTE(self, args):
        # The order of these is important! ;)
        self.send("Shutting up for now.")
        self.channel.muted = True
    command_MUTE.usage = "mute - suppress all messages until a corresponding 'unmute' is issued"

    def command_UNMUTE(self, args):
        if self.channel.muted:
            # The order of these is important! ;)
            self.channel.muted = False
            self.send("I'm baaaaaaaaaaack!")
        else:
            self.send(
                "You hadn't told me to be quiet, but it's the thought that counts, right?")
    command_UNMUTE.usage = "unmute - disable a previous 'mute'"

    def command_DESTROY(self, args):
        if self.bot.nickname not in args:
            self.act("readies phasers")

    def command_HUSTLE(self, args):
        self.act("does the hustle")
    command_HUSTLE.usage = "dondon on #qutebrowser: qutebrowser-bb needs to learn to do the hustle"


class IrcStatusBot(StatusBot, irc.IRCClient):

    """I represent the buildbot to an IRC server.
    """

    contactClass = IRCContact
    channelClass = IRCChannel

    def __init__(self, nickname, password, join_channels, pm_to_nicks,
                 noticeOnChannel, *args, useColors=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.nickname = nickname
        self.join_channels = join_channels
        self.pm_to_nicks = pm_to_nicks
        self.password = password
        self.hasQuit = 0
        self.noticeOnChannel = noticeOnChannel
        self.useColors = useColors
        self._keepAliveCall = task.LoopingCall(
            lambda: self.ping(self.nickname))

    def connectionMade(self):
        super().connectionMade()
        self._keepAliveCall.start(60)

    def connectionLost(self, reason):
        if self._keepAliveCall.running:
            self._keepAliveCall.stop()
        super().connectionLost(reason)

    # The following methods are called when we write something.
    def groupSend(self, channel, message):
        if self.noticeOnChannel:
            self.notice(channel, message)
        else:
            self.msg(channel, message)

    def groupDescribe(self, channel, action):
        self.describe(channel, action)

    def getContact(self, user, channel=None):
        # nicknames and channel names are case insensitive
        if user:
            user = user.lower()
        if channel:
            channel = channel.lower()
        return super().getContact(user, channel)

    # the following irc.IRCClient methods are called when we have input
    def privmsg(self, user, channel, message):
        user = user.split('!', 1)[0]  # rest is ~user@hostname
        # channel is '#twisted' or 'buildbot' (for private messages)
        if channel == self.nickname:
            # private message
            contact = self.getContact(user=user)
            d = contact.handleMessage(message)
            return d
        # else it's a broadcast message, maybe for us, maybe not. 'channel'
        # is '#twisted' or the like.
        contact = self.getContact(user=user, channel=channel)
        if message.startswith("%s:" % self.nickname) or message.startswith("%s," % self.nickname):
            message = message[len("%s:" % self.nickname):]
            d = contact.handleMessage(message)
            return d

    def action(self, user, channel, data):
        user = user.split('!', 1)[0]  # rest is ~user@hostname
        # somebody did an action (/me actions) in the broadcast channel
        contact = self.getContact(user=user, channel=channel)
        if self.nickname in data:
            contact.handleAction(data)

    def signedOn(self):
        if self.password:
            self.msg("Nickserv", "IDENTIFY " + self.password)
        for c in self.join_channels:
            if isinstance(c, dict):
                channel = c.get('channel', None)
                password = c.get('password', None)
            else:
                channel = c
                password = None
            self.join(channel=channel, key=password)
        for c in self.pm_to_nicks:
            contact = self.getContact(c)
            contact.channel.add_notification_events(self.notify_events)

    def joined(self, channel):
        self.log("I have joined %s" % (channel,))
        # trigger contact constructor, which in turn subscribes to notify events
        channel = self.getChannel(channel=channel)
        channel.add_notification_events(self.notify_events)

    def left(self, channel):
        self.log("I have left %s" % (channel,))

    def kickedFrom(self, channel, kicker, message):
        self.log("I have been kicked from %s by %s: %s" % (channel,
                                                           kicker,
                                                           message))

    def userLeft(self, user, channel):
        if user: user = user.lower()
        if channel: channel = channel.lower()
        if (channel, user) in self.contacts:
            del self.contacts[(channel, user)]

    def userKicked(self, kickee, channel, kicker, message):
        self.userLeft(kickee, channel)

    def userQuit(self, user, quitMessage=None):
        if user: user = user.lower()
        for c,u in list(self.contacts):
            if u == user:
                del self.contacts[(c,u)]

    results_colors = {
        SUCCESS: 'GREEN',
        WARNINGS: 'YELLOW',
        FAILURE: 'RED',
        EXCEPTION: 'PURPLE',
        RETRY: 'AQUA_LIGHT',
        CANCELLED: 'PINK',
    }

    short_results_descriptions = {
        SUCCESS: ", Success",
        WARNINGS: ", Warnings",
        FAILURE: ", Failure",
        EXCEPTION: ", Exception",
        RETRY: ", Retry",
        CANCELLED: ", Cancelled",
    }

    def format_build_status(self, build, short=False):
        br = build['results']
        if short:
            text = self.short_results_descriptions[br]
        else:
            text = self.results_descriptions[br]
        if self.bot.useColors:
            return "\x03{:d}{}\x0f".format(
                _irc_colors.index(self.results_colors[br]),
                text)
        else:
            return text


class IrcStatusFactory(ThrottledClientFactory):
    protocol = IrcStatusBot

    shuttingDown = False
    p = None

    def __init__(self, nickname, password, join_channels, pm_to_nicks, authz, tags, notify_events,
                 noticeOnChannel=False,
                 useRevisions=False, showBlameList=False,
                 parent=None,
                 lostDelay=None, failedDelay=None, useColors=True):
        super().__init__(lostDelay=lostDelay, failedDelay=failedDelay)
        self.nickname = nickname
        self.password = password
        self.join_channels = join_channels
        self.pm_to_nicks = pm_to_nicks
        self.tags = tags
        self.authz = authz
        self.parent = parent
        self.notify_events = notify_events
        self.noticeOnChannel = noticeOnChannel
        self.useRevisions = useRevisions
        self.showBlameList = showBlameList
        self.useColors = useColors

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['p']
        return d

    def shutdown(self):
        self.shuttingDown = True
        if self.p:
            self.p.quit("buildmaster reconfigured: bot disconnecting")

    def buildProtocol(self, address):
        if self.p:
            self.p.disownServiceParent()

        p = self.protocol(self.nickname, self.password,
                          self.join_channels, self.pm_to_nicks,
                          self.noticeOnChannel, self.authz,
                          self.tags, self.notify_events,
                          useColors=self.useColors,
                          useRevisions=self.useRevisions,
                          showBlameList=self.showBlameList)
        p.setServiceParent(self.parent)
        p.factory = self
        self.p = p
        return p

    # TODO: I think a shutdown that occurs while the connection is being
    # established will make this explode

    def clientConnectionLost(self, connector, reason):
        if self.shuttingDown:
            log.msg("not scheduling reconnection attempt")
            return
        super().clientConnectionLost(connector, reason)

    def clientConnectionFailed(self, connector, reason):
        if self.shuttingDown:
            log.msg("not scheduling reconnection attempt")
            return
        super().clientConnectionFailed(connector, reason)


class IRC(service.BuildbotService):
    name = "IRC"
    in_test_harness = False
    f = None
    compare_attrs = ("host", "port", "nick", "password", "authz",
                     "channels", "pm_to_nicks", "useSSL",
                     "useRevisions", "tags", "useColors",
                     "lostDelay", "failedDelay")
    secrets = ['password']

    def checkConfig(self, host, nick, channels, pm_to_nicks=None, port=6667,
                    authz=None, tags=None, password=None, notify_events=None,
                    showBlameList=True, useRevisions=False,
                    useSSL=False, lostDelay=None, failedDelay=None, useColors=True,
                    noticeOnChannel=False, **kwargs
                    ):
        deprecated_params = list(kwargs)
        if deprecated_params:
            config.error("%s are deprecated" % (",".join(deprecated_params)))

        if noticeOnChannel not in (True, False):
            config.error("noticeOnChannel must be boolean, not %r" %
                         (noticeOnChannel,))
        if useSSL:
            # SSL client needs a ClientContextFactory for some SSL mumbo-jumbo
            ssl.ensureHasSSL(self.__class__.__name__)
        if authz is not None:
            for acl in authz.values():
                if not isinstance(acl, (list, tuple, bool)):
                    config.error("authz values must be bool or a list of nicks")

    def reconfigService(self, host, nick, channels, pm_to_nicks=None, port=6667,
                        authz=None, tags=None, password=None, notify_events=None,
                        showBlameList=True, useRevisions=False,
                        useSSL=False, lostDelay=None, failedDelay=None, useColors=True,
                        noticeOnChannel=False, **kwargs
                        ):

        # need to stash these so we can detect changes later
        self.host = host
        self.port = port
        self.nick = nick
        self.join_channels = channels
        if pm_to_nicks is None: pm_to_nicks = []
        self.pm_to_nicks = pm_to_nicks
        self.password = password
        self.authz = authz
        self.useRevisions = useRevisions
        self.tags = tags
        if notify_events is None: notify_events = {}
        self.notify_events = notify_events
        self.noticeOnChannel = noticeOnChannel

        # This function is only called in case of reconfig with changes
        # We don't try to be smart here. Just restart the bot if config has
        # changed.
        if self.f is not None:
            self.f.shutdown()
        self.f = IrcStatusFactory(self.nick, self.password,
                                  self.join_channels, self.pm_to_nicks,
                                  self.authz, self.tags,
                                  self.notify_events, parent=self,
                                  noticeOnChannel=noticeOnChannel,
                                  useRevisions=useRevisions,
                                  showBlameList=showBlameList,
                                  lostDelay=lostDelay,
                                  failedDelay=failedDelay,
                                  useColors=useColors)

        if useSSL:
            cf = ssl.ClientContextFactory()
            c = internet.SSLClient(self.host, self.port, self.f, cf)
        else:
            c = internet.TCPClient(self.host, self.port, self.f)

        c.setServiceParent(self)
