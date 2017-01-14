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

from twisted.application import internet
from twisted.internet import task
from twisted.python import log
from twisted.words.protocols import irc

from buildbot import config
from buildbot.reporters.words import StatusBot
from buildbot.reporters.words import ThrottledClientFactory
from buildbot.util import service
from buildbot.util import ssl


class UsageError(ValueError):

    def __init__(self, string="Invalid usage", *more):
        ValueError.__init__(self, string, *more)


class IrcStatusBot(StatusBot, irc.IRCClient):

    """I represent the buildbot to an IRC server.
    """

    def __init__(self, nickname, password, channels, pm_to_nicks, *args, **kwargs):
        StatusBot.__init__(self, *args, **kwargs)
        self.nickname = nickname
        self.channels = channels
        self.pm_to_nicks = pm_to_nicks
        self.password = password
        self.hasQuit = 0
        self._keepAliveCall = task.LoopingCall(
            lambda: self.ping(self.nickname))

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self._keepAliveCall.start(60)

    def connectionLost(self, reason):
        if self._keepAliveCall.running:
            self._keepAliveCall.stop()
        irc.IRCClient.connectionLost(self, reason)

    # The following methods are called when we write something.
    def groupChat(self, channel, message):
        self.notice(channel, message.encode('utf-8', 'replace'))

    def chat(self, user, message):
        self.msg(user, message.encode('utf-8', 'replace'))

    def groupDescribe(self, channel, action):
        self.describe(channel, action.encode('utf-8', 'replace'))

    def getContact(self, user=None, channel=None):
        # nicknames and channel names are case insensitive
        if user:
            user = user.lower()
        if channel:
            channel = channel.lower()
        return StatusBot.getContact(self, user, channel)

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
        for c in self.channels:
            if isinstance(c, dict):
                channel = c.get('channel', None)
                password = c.get('password', None)
            else:
                channel = c
                password = None
            self.join(channel=channel, key=password)
        for c in self.pm_to_nicks:
            self.getContact(c)

    def joined(self, channel):
        self.log("I have joined %s" % (channel,))
        # trigger contact constructor, which in turn subscribes to notify events
        self.getContact(channel=channel)

    def left(self, channel):
        self.log("I have left %s" % (channel,))

    def kickedFrom(self, channel, kicker, message):
        self.log("I have been kicked from %s by %s: %s" % (channel,
                                                           kicker,
                                                           message))


class IrcStatusFactory(ThrottledClientFactory):
    protocol = IrcStatusBot

    shuttingDown = False
    p = None

    def __init__(self, nickname, password, channels, pm_to_nicks, tags, notify_events,
                 useRevisions=False, showBlameList=False,
                 parent=None,
                 lostDelay=None, failedDelay=None, useColors=True, allowShutdown=False):
        ThrottledClientFactory.__init__(self, lostDelay=lostDelay,
                                        failedDelay=failedDelay)
        self.nickname = nickname
        self.password = password
        self.channels = channels
        self.pm_to_nicks = pm_to_nicks
        self.tags = tags
        self.parent = parent
        self.notify_events = notify_events
        self.useRevisions = useRevisions
        self.showBlameList = showBlameList
        self.useColors = useColors
        self.allowShutdown = allowShutdown

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
                          self.channels, self.pm_to_nicks,
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
        ThrottledClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        if self.shuttingDown:
            log.msg("not scheduling reconnection attempt")
            return
        ThrottledClientFactory.clientConnectionFailed(self, connector, reason)


class IRC(service.BuildbotService):
    name = "IRC"
    in_test_harness = False
    f = None
    compare_attrs = ("host", "port", "nick", "password",
                     "channels", "pm_to_nicks", "allowForce", "useSSL",
                     "useRevisions", "tags", "useColors",
                     "lostDelay", "failedDelay", "allowShutdown")

    def checkConfig(self, host, nick, channels, pm_to_nicks=None, port=6667,
                    allowForce=False, tags=None, password=None, notify_events=None,
                    showBlameList=True, useRevisions=False,
                    useSSL=False, lostDelay=None, failedDelay=None, useColors=True,
                    allowShutdown=False, **kwargs
                    ):
        deprecated_params = list(kwargs)
        if deprecated_params:
            config.error("%s are deprecated" % (",".join(deprecated_params)))

        if allowForce not in (True, False):
            config.error("allowForce must be boolean, not %r" % (allowForce,))
        if allowShutdown not in (True, False):
            config.error("allowShutdown must be boolean, not %r" %
                         (allowShutdown,))
        if useSSL:
            # SSL client needs a ClientContextFactory for some SSL mumbo-jumbo
            ssl.ensureHasSSL(self.__class__.__name__)

    def reconfigService(self, host, nick, channels, pm_to_nicks=None, port=6667,
                        allowForce=False, tags=None, password=None, notify_events=None,
                        showBlameList=True, useRevisions=False,
                        useSSL=False, lostDelay=None, failedDelay=None, useColors=True,
                        allowShutdown=False, **kwargs
                        ):

        # need to stash these so we can detect changes later
        self.host = host
        self.port = port
        self.nick = nick
        self.channels = channels
        if pm_to_nicks is None:
            pm_to_nicks = []
        self.pm_to_nicks = pm_to_nicks
        self.password = password
        self.allowForce = allowForce
        self.useRevisions = useRevisions
        self.tags = tags
        if notify_events is None:
            notify_events = {}
        self.notify_events = notify_events
        self.allowShutdown = allowShutdown

        # This function is only called in case of reconfig with changes
        # We don't try to be smart here. Just restart the bot if config has
        # changed.
        if self.f is not None:
            self.f.shutdown()
        self.f = IrcStatusFactory(self.nick, self.password,
                                  self.channels, self.pm_to_nicks,
                                  self.tags, self.notify_events,
                                  parent=self,
                                  useRevisions=useRevisions,
                                  showBlameList=showBlameList,
                                  lostDelay=lostDelay,
                                  failedDelay=failedDelay,
                                  useColors=useColors,
                                  allowShutdown=allowShutdown)

        if useSSL:
            cf = ssl.ClientContextFactory()
            c = internet.SSLClient(self.host, self.port, self.f, cf)
        else:
            c = internet.TCPClient(self.host, self.port, self.f)

        c.setServiceParent(self)
