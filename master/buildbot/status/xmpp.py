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

# Deliver build status to a Jabber MUC (multi-user chat room).

from __future__ import absolute_import

from zope.interface import implements
from twisted.python import log
from twisted.internet import task
from twisted.words.protocols.jabber.jid import JID

# Twisted Words 11.0 lacks high-level support for XMPP.  For that, we
# use Wokkel.  This module should eventually be merged into words.py
# when Twisted Words integrates the features we need from Wokkel.
from wokkel.client import XMPPClient
from wokkel.muc import MUCClient
from wokkel.ping import PingHandler
from wokkel.subprotocols import XMPPHandler

from buildbot import interfaces
from buildbot.interfaces import IStatusReceiver
from buildbot.status import base, words

class KeepAliveHandler(XMPPHandler):
    """
    This handler implements client-to-server pings to prevent timeouts

    Example: The OpenFire jabberd will disconnect you after 6 minutes
    if you don't send active pings

    @see https://developer.pidgin.im/ticket/10767
    @see https://github.com/dustin/wokkel/blob/master/wokkel/keepalive.py
    """

    interval = 300
    lc = None

    def connectionInitialized(self):
        self.lc = task.LoopingCall(self.ping)
        self.lc.start(self.interval)

    def connectionLost(self, *args):
        if self.lc and self.lc.running:
            self.lc.stop()

    def ping(self):
        self.send(" ")

class JabberStatusBot(words.StatusBot, MUCClient):

    def __init__(self, mucs, categories, notify_events, status, noticeOnChannel=False,
            useRevisions=False, showBlameList=False):
        # colors make sense for IRC only atm, so disable them for Jabber
        words.StatusBot.__init__(self, status, categories, notify_events,
            noticeOnChannel, useRevisions, showBlameList, useColors=False)
        MUCClient.__init__(self)

        self.mucs = mucs

    def getCurrentNickname(self, contact):
        roomJID = contact.channel
        room = self._getRoom(roomJID)
        return room.nick

    def connectionInitialized(self):
        MUCClient.connectionInitialized(self)
        for m in self.mucs:
            (muc, nick) = (m['muc'], m['nick'])
            MUCClient.join(self, JID(muc), nick)

    def connectionLost(self, reason):
        MUCClient.connectionLost(self, reason)
        self.log("Got disconnected: %s" % (reason,))

    def userJoinedRoom(self, room, user):
        # ignore all but our own
        if user.nick != room.nick:
            return

        self.log("I have joined %s" % (room.roomJID.userhost(),))
        self.getContact(user=None, channel=room.roomJID)

    def userLeftRoom(self, room, user):
        # ignore all but our own
        if user.nick != room.nick:
            return

        self.log("I have left %s" % (room.roomJID,))

    def receivedGroupChat(self, room, user, message):
        try:
            # Ignore our own messages sent to the MUC.  'tis a bit silly
            # that we can fire our own received message handler...
            if user.nick == room.nick:
                return
        except AttributeError:
            return # Some kind of status message.  Ignore this, too.

        contact = self.getContact(user=user.nick, channel=room.occupantJID.userhostJID())
        body = message.body
        if body.startswith("/me") and body.endswith("s "+ room.nick):
            contact.handleAction(body)
        if body.startswith("%s:" % room.nick) or body.startswith("%s," % room.nick):
            body = body[len("%s:" % room.nick):]
            contact.handleMessage(body)

    def groupChat(self, channel, message):
        MUCClient.groupChat(self, channel, message)

    def describe(self, dest, action):
        self.groupChat(dest, "/me %s" % action)

class Jabber(base.StatusReceiver, XMPPClient):
    """
    I represent a status target for Jabber services.

    It can be used to connect to a Jabber server.
    A list of MUCs can be specified that will be joined on logon.

    @type host: string
    @cvar host: the host where the Jabber service lives, e.g. "localhost"
    @type jid: string
    @cvar jid: the JID that is used to login, in the form "nick@host/resource"
    @type password: string
    @cvar password: password that is used to login to the service
    @type mucs: list of dicts
    @ivar mucs: MUC list, specifying the chat and the nick to be used,
        e.g. [{'muc':chat@conference.example.com,'nick':'user1'}]
    @type port: integer
    @ivar port: port of the Jabber service (optional)
    """

    implements(IStatusReceiver)

    debug = False

    compare_attrs = ['host', 'jid', 'password', 'mucs', 'port',
      'allowForce', 'categories', 'notify_events']

    def __init__(self, host, jid, password, mucs, port=5222,
                 allowForce=False, categories=None, notify_events={},
                 noticeOnChannel=False, useRevisions=False, showBlameList=False):
        assert allowForce in (True, False)

        # Stash these so we can detect changes later.
        self.password = password
        assert(isinstance(mucs, list))
        self.mucs = mucs
        self.allowForce = allowForce
        self.categories = categories
        self.notify_events = notify_events

        if not isinstance(jid, JID):
            jid = JID(str(jid))

        log.msg("[Jabber] Initiating XMPP connection to %s:%s" % (host, port))

        XMPPClient.__init__(self, jid, self.password, host, port)
        self.logTraffic = self.debug

        # add ping handler
        ping_handler = PingHandler()
        self.addHandler(ping_handler)
        ping_handler.setHandlerParent(self)

        # add keep alive handler
        keepalive_handler = KeepAliveHandler()
        self.addHandler(keepalive_handler)
        keepalive_handler.setHandlerParent(self)

        # add MUC handler
        bot = JabberStatusBot(self.mucs, self.categories,
                              self.notify_events, None, noticeOnChannel=noticeOnChannel,
                              useRevisions=useRevisions, showBlameList=showBlameList
                              )
        self.addHandler(bot)
        bot.setHandlerParent(self)
        self.bot = bot

    def setServiceParent(self, parent):
        base.StatusReceiver.setServiceParent(self, parent)
        self.bot.status = parent
        self.bot.master = parent.master
        if self.allowForce:
            self.bot.control = interfaces.IControl(self.master)
        XMPPClient.setServiceParent(self, parent)
