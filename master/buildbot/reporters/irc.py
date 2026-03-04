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

import base64
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import cast

from twisted.application import internet
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.words.protocols import irc

from buildbot import config
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters.words import Channel
from buildbot.reporters.words import Contact
from buildbot.reporters.words import StatusBot
from buildbot.reporters.words import ThrottledClientFactory
from buildbot.reporters.words import dangerousCommand
from buildbot.util import service
from buildbot.util import ssl

if TYPE_CHECKING:
    from collections.abc import Sequence

    from twisted.internet.interfaces import IReactorTime
    from twisted.python.failure import Failure

    from buildbot.util.twisted import InlineCallbacksType


class UsageError(ValueError):
    # pylint: disable=useless-super-delegation
    def __init__(self, string: str = "Invalid usage", *more: Any) -> None:
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
    'PINK',
    'DARK_GRAY',
    'LIGHT_GRAY',
)


class IRCChannel(Channel):
    def __init__(self, bot: Any, channel: Any) -> None:
        super().__init__(bot, channel)
        self.muted = False

    def send(self, message: Any, **kwargs: Any) -> None:
        if self.id[0] in irc.CHANNEL_PREFIXES:
            send = self.bot.groupSend
        else:
            send = self.bot.msg
        if not self.muted:
            send(self.id, message)

    def act(self, action: Any) -> None:
        if self.muted:
            return
        self.bot.groupDescribe(self.id, action)


class IRCContact(Contact):
    def __init__(self, user: Any, channel: Any = None) -> None:
        if channel is None:
            channel = user
        super().__init__(user, channel)

    def act(self, action: Any) -> Any:
        return self.channel.act(action)

    def handleAction(self, action: str) -> None:
        # this is sent when somebody performs an action that mentions the
        # buildbot (like '/me kicks buildbot'). 'self.user' is the name/nick/id of
        # the person who performed the action, so if their action provokes a
        # response, they can be named.  This is 100% silly.
        if not action.endswith("s " + self.bot.nickname):
            return
        words = action.split()
        verb = words[-2]
        if verb == "kicks":
            response = f"{verb} back"
        elif verb == "threatens":
            response = f"hosts a red wedding for {self.user_id}"
        else:
            response = f"{verb} {self.user_id} too"
        self.act(response)

    @defer.inlineCallbacks
    def op_required(self, command: str) -> InlineCallbacksType[bool]:
        if self.is_private_chat or self.user_id in self.bot.authz.get(command.upper(), ()):
            return False
        ops = yield self.bot.getChannelOps(self.channel.id)
        return self.user_id not in ops

    # IRC only commands

    @dangerousCommand
    def command_JOIN(self, args: Any, **kwargs: Any) -> None:
        """join a channel"""
        args = self.splitArgs(args)
        for channel in args:
            self.bot.join(channel)

    command_JOIN.usage = "join #channel - join a channel #channel"  # type: ignore[attr-defined]

    @dangerousCommand
    def command_LEAVE(self, args: Any, **kwargs: Any) -> None:
        """leave a channel"""
        args = self.splitArgs(args)
        for channel in args:
            self.bot.leave(channel)

    command_LEAVE.usage = "leave #channel - leave a channel #channel"  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def command_MUTE(self, args: Any, **kwargs: Any) -> InlineCallbacksType[None]:
        if (yield self.op_required('mute')):
            yield self.send(
                "Only channel operators or explicitly allowed users "
                f"can mute me here, {self.user_id}... Blah, blah, blah..."
            )
            return
        # The order of these is important! ;)
        yield self.send("Shutting up for now.")
        self.channel.muted = True

    command_MUTE.usage = "mute - suppress all messages until a corresponding 'unmute' is issued"  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def command_UNMUTE(self, args: Any, **kwargs: Any) -> InlineCallbacksType[None]:
        if self.channel.muted:
            if (yield self.op_required('mute')):
                return
            # The order of these is important! ;)
            self.channel.muted = False
            yield self.send("I'm baaaaaaaaaaack!")
        else:
            yield self.send(
                "No one had told me to be quiet, but it's the thought that counts, right?"
            )

    command_UNMUTE.usage = "unmute - disable a previous 'mute'"  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    @Contact.overrideCommand
    def command_NOTIFY(self, args: Any, **kwargs: Any) -> InlineCallbacksType[None]:
        if not self.is_private_chat:
            argv = self.splitArgs(args)
            if argv and argv[0] in ('on', 'off') and (yield self.op_required('notify')):
                yield self.send(
                    "Only channel operators can change notified events for this "
                    f"channel. And you, {self.user_id}, are neither!"
                )
                return
        super().command_NOTIFY(args, **kwargs)

    def command_DANCE(self, args: Any, **kwargs: Any) -> None:
        """dance, dance academy..."""
        cast("IReactorTime", reactor).callLater(1.0, self.send, "<(^.^<)")
        cast("IReactorTime", reactor).callLater(2.0, self.send, "<(^.^)>")
        cast("IReactorTime", reactor).callLater(3.0, self.send, "(>^.^)>")
        cast("IReactorTime", reactor).callLater(3.5, self.send, "(7^.^)7")
        cast("IReactorTime", reactor).callLater(5.0, self.send, "(>^.^<)")

    def command_DESTROY(self, args: Any) -> None:
        if self.bot.nickname not in args:
            self.act("readies phasers")
        else:
            self.send(f"Better destroy yourself, {self.user_id}!")

    def command_HUSTLE(self, args: Any) -> None:
        self.act("does the hustle")

    command_HUSTLE.usage = "dondon on #qutebrowser: qutebrowser-bb needs to learn to do the hustle"  # type: ignore[attr-defined]


class IrcStatusBot(StatusBot, irc.IRCClient):
    """I represent the buildbot to an IRC server."""

    contactClass = IRCContact
    channelClass = IRCChannel

    def __init__(
        self,
        nickname: str,
        password: str | None,
        join_channels: list[Any],
        pm_to_nicks: list[str],
        noticeOnChannel: bool,
        *args: Any,
        useColors: bool = False,
        useSASL: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.nickname = nickname
        self.join_channels = join_channels
        self.pm_to_nicks = pm_to_nicks
        self.password = password  # type: ignore[assignment]
        self.hasQuit = 0
        self.noticeOnChannel = noticeOnChannel
        self.useColors = useColors
        self.useSASL = useSASL
        self._keepAliveCall = task.LoopingCall(lambda: self.ping(self.nickname))
        self._channel_names: dict[str, tuple[list[Any], list[str]]] = {}

    def register(self, nickname: str, hostname: str = "foo", servername: str = "bar") -> None:
        if not self.useSASL:
            super().register(nickname, hostname, servername)
            return

        if self.password is not None:
            self.sendLine("CAP REQ :sasl")
        self.setNick(nickname)
        if self.username is None:
            self.username = nickname  # type: ignore[assignment]
        self.sendLine(f"USER {self.username} {hostname} {servername} :{self.realname}")
        if self.password is not None:
            self.sendLine("AUTHENTICATE PLAIN")

    def irc_AUTHENTICATE(self, prefix: str, params: list[str]) -> None:
        nick = self.nickname.encode()
        assert self.password is not None
        passwd = self.password.encode()
        code = base64.b64encode(nick + b'\0' + nick + b'\0' + passwd)
        self.sendLine("AUTHENTICATE " + code.decode())
        self.sendLine("CAP END")

    def connectionMade(self) -> None:
        super().connectionMade()
        self._keepAliveCall.start(60)

    def connectionLost(self, reason: Failure) -> None:  # type: ignore[override]
        if self._keepAliveCall.running:
            self._keepAliveCall.stop()
        super().connectionLost(reason)

    # The following methods are called when we write something.
    def groupSend(self, channel: str, message: str) -> None:
        if self.noticeOnChannel:
            self.notice(channel, message)
        else:
            self.msg(channel, message)

    def groupDescribe(self, channel: str, action: str) -> None:
        self.describe(channel, action)

    def getContact(self, user: str, channel: str | None = None) -> Any:
        # nicknames and channel names are case insensitive
        user = user.lower()
        if channel is None:
            channel = user
        channel = channel.lower()
        return super().getContact(user, channel)

    # the following irc.IRCClient methods are called when we have input
    def privmsg(self, user: str, channel: str, message: str) -> Any:
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
        if message.startswith(f"{self.nickname}:") or message.startswith(f"{self.nickname},"):
            message = message[len(f"{self.nickname}:") :]
            d = contact.handleMessage(message)
            return d
        return None

    def action(self, user: str, channel: str, data: str) -> None:
        user = user.split('!', 1)[0]  # rest is ~user@hostname
        # somebody did an action (/me actions) in the broadcast channel
        contact = self.getContact(user=user, channel=channel)
        if self.nickname in data:
            contact.handleAction(data)

    def signedOn(self) -> None:
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
        self.loadState()

    def getNames(self, channel: str) -> defer.Deferred[list[str]]:
        channel = channel.lower()
        d: defer.Deferred[list[str]] = defer.Deferred()
        callbacks = self._channel_names.setdefault(channel, ([], []))[0]
        callbacks.append(d)
        self.sendLine(f"NAMES {channel}")
        return d

    def irc_RPL_NAMREPLY(self, prefix: str, params: list[str]) -> None:
        channel = params[2].lower()
        if channel not in self._channel_names:
            return
        nicks = params[3].split(' ')
        nicklist = self._channel_names[channel][1]
        nicklist += nicks

    def irc_RPL_ENDOFNAMES(self, prefix: str, params: list[str]) -> None:
        channel = params[1].lower()
        try:
            callbacks, namelist = self._channel_names.pop(channel)
        except KeyError:
            return
        for cb in callbacks:
            cb.callback(namelist)

    @defer.inlineCallbacks
    def getChannelOps(self, channel: str) -> InlineCallbacksType[list[str]]:
        names = yield self.getNames(channel)
        return [n[1:] for n in names if n[0] in '@&~%']

    def joined(self, channel: str) -> None:
        self.log(f"Joined {channel}")
        # trigger contact constructor, which in turn subscribes to notify events
        channel_obj = self.getChannel(channel=channel)
        channel_obj.add_notification_events(self.notify_events)

    def left(self, channel: str) -> None:
        self.log(f"Left {channel}")

    def kickedFrom(self, channel: str, kicker: str, message: str) -> None:
        self.log(f"I have been kicked from {channel} by {kicker}: {message}")

    def userLeft(self, user: str, channel: str) -> None:
        if user:
            user = user.lower()
        if channel:
            channel = channel.lower()
        if (channel, user) in self.contacts:
            del self.contacts[(channel, user)]

    def userKicked(self, kickee: str, channel: str, kicker: str, message: str) -> None:
        self.userLeft(kickee, channel)

    def userQuit(self, user: str, quitMessage: str | None = None) -> None:
        if user:
            user = user.lower()
        for c, u in list(self.contacts):
            if u == user:
                del self.contacts[(c, u)]

    results_colors = {
        SUCCESS: 'GREEN',
        WARNINGS: 'YELLOW',
        FAILURE: 'RED',
        SKIPPED: 'ROYAL_BLUE',
        EXCEPTION: 'PURPLE',
        RETRY: 'AQUA_LIGHT',
        CANCELLED: 'PINK',
    }

    short_results_descriptions = {
        SUCCESS: ", Success",
        WARNINGS: ", Warnings",
        FAILURE: ", Failure",
        SKIPPED: ", Skipped",
        EXCEPTION: ", Exception",
        RETRY: ", Retry",
        CANCELLED: ", Cancelled",
    }

    def format_build_status(self, build: Any, short: bool = False) -> str:
        br = build['results']
        if short:
            text = self.short_results_descriptions[br]
        else:
            text = self.results_descriptions[br]
        if self.useColors:
            return f"\x03{_irc_colors.index(self.results_colors[br])}{text}\x0f"
        else:
            return text


class IrcStatusFactory(ThrottledClientFactory):
    protocol = IrcStatusBot  # type: ignore[assignment]

    shuttingDown = False
    p = None

    def __init__(
        self,
        nickname: str,
        password: str | None,
        join_channels: list[Any],
        pm_to_nicks: list[str],
        authz: dict[str, Any],
        tags: Any,
        notify_events: dict[str, Any],
        noticeOnChannel: bool = False,
        useRevisions: bool = False,
        showBlameList: bool = False,
        useSASL: bool = False,
        parent: Any = None,
        lostDelay: int | None = None,
        failedDelay: int | None = None,
        useColors: bool = True,
    ) -> None:
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
        self.useSASL = useSASL

    def __getstate__(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        del d['p']
        return d

    def shutdown(self) -> None:
        self.shuttingDown = True
        if self.p:
            self.p.quit("buildmaster reconfigured: bot disconnecting")

    def buildProtocol(self, address: Any) -> IrcStatusBot:
        if self.p:
            self.p.disownServiceParent()

        p = self.protocol(
            self.nickname,
            self.password,
            self.join_channels,
            self.pm_to_nicks,
            self.noticeOnChannel,
            self.authz,
            self.tags,
            self.notify_events,
            useColors=self.useColors,
            useSASL=self.useSASL,
            useRevisions=self.useRevisions,
            showBlameList=self.showBlameList,
        )
        p.setServiceParent(self.parent)
        p.factory = self
        self.p = p
        return p

    # TODO: I think a shutdown that occurs while the connection is being
    # established will make this explode

    def clientConnectionLost(self, connector: Any, reason: Any) -> None:
        if self.shuttingDown:
            log.msg("not scheduling reconnection attempt")
            return
        super().clientConnectionLost(connector, reason)

    def clientConnectionFailed(self, connector: Any, reason: Any) -> None:
        if self.shuttingDown:
            log.msg("not scheduling reconnection attempt")
            return
        super().clientConnectionFailed(connector, reason)


class IRC(service.BuildbotService):
    name = "IRC"
    in_test_harness = False
    f = None
    compare_attrs: ClassVar[Sequence[str]] = (
        "host",
        "port",
        "nick",
        "password",
        "authz",
        "channels",
        "pm_to_nicks",
        "useSSL",
        "useSASL",
        "useRevisions",
        "tags",
        "useColors",
        "allowForce",
        "allowShutdown",
        "lostDelay",
        "failedDelay",
    )
    secrets = ['password']

    def checkConfig(
        self,
        host: str,
        nick: str,
        channels: list[Any],
        pm_to_nicks: list[str] | None = None,
        port: int = 6667,
        allowForce: bool | None = None,
        tags: Any = None,
        password: str | None = None,
        notify_events: dict[str, Any] | None = None,
        showBlameList: bool = True,
        useRevisions: bool = False,
        useSSL: bool = False,
        useSASL: bool = False,
        lostDelay: int | None = None,
        failedDelay: int | None = None,
        useColors: bool = True,
        allowShutdown: bool | None = None,
        noticeOnChannel: bool = False,
        authz: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        deprecated_params = list(kwargs)
        if deprecated_params:
            config.error(f'{",".join(deprecated_params)} are deprecated')

        # deprecated
        if allowForce is not None:
            if authz is not None:
                config.error("If you specify authz, you must not use allowForce anymore")
            if allowForce not in (True, False):
                config.error(f"allowForce must be boolean, not {allowForce!r}")
            log.msg('IRC: allowForce is deprecated: use authz instead')
        if allowShutdown is not None:
            if authz is not None:
                config.error("If you specify authz, you must not use allowShutdown anymore")
            if allowShutdown not in (True, False):
                config.error(f"allowShutdown must be boolean, not {allowShutdown!r}")
            log.msg('IRC: allowShutdown is deprecated: use authz instead')
        # ###

        if noticeOnChannel not in (True, False):
            config.error(f"noticeOnChannel must be boolean, not {noticeOnChannel!r}")
        if useSSL:
            # SSL client needs a ClientContextFactory for some SSL mumbo-jumbo
            ssl.ensureHasSSL(self.__class__.__name__)
        if authz is not None:
            for acl in authz.values():
                if not isinstance(acl, (list, tuple, bool)):
                    config.error("authz values must be bool or a list of nicks")

    def reconfigService(  # type: ignore[override]
        self,
        host: str,
        nick: str,
        channels: list[Any],
        pm_to_nicks: list[str] | None = None,
        port: int = 6667,
        allowForce: bool | None = None,
        tags: Any = None,
        password: str | None = None,
        notify_events: dict[str, Any] | None = None,
        showBlameList: bool = True,
        useRevisions: bool = False,
        useSSL: bool = False,
        useSASL: bool = False,
        lostDelay: int | None = None,
        failedDelay: int | None = None,
        useColors: bool = True,
        allowShutdown: bool | None = None,
        noticeOnChannel: bool = False,
        authz: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        # need to stash these so we can detect changes later
        self.host = host
        self.port = port
        self.nick = nick
        self.join_channels = channels
        if pm_to_nicks is None:
            pm_to_nicks = []
        self.pm_to_nicks = pm_to_nicks
        self.password = password
        if authz is None:
            self.authz: dict[Any, Any] = {}
        else:
            self.authz = authz
        self.useRevisions = useRevisions
        self.tags = tags
        if notify_events is None:
            notify_events = {}
        self.notify_events = notify_events
        self.noticeOnChannel = noticeOnChannel

        # deprecated...
        if allowForce is not None:
            self.authz[('force', 'stop')] = allowForce  # type: ignore[index]
        if allowShutdown is not None:
            self.authz[('shutdown')] = allowShutdown
        # ###

        # This function is only called in case of reconfig with changes
        # We don't try to be smart here. Just restart the bot if config has
        # changed.
        if self.f is not None:
            self.f.shutdown()
        self.f = IrcStatusFactory(
            self.nick,
            self.password,
            self.join_channels,
            self.pm_to_nicks,
            self.authz,
            self.tags,
            self.notify_events,
            parent=self,
            noticeOnChannel=noticeOnChannel,
            useRevisions=useRevisions,
            useSASL=useSASL,
            showBlameList=showBlameList,
            lostDelay=lostDelay,
            failedDelay=failedDelay,
            useColors=useColors,
        )

        if useSSL:
            cf = ssl.ClientContextFactory()
            c: Any = internet.SSLClient(self.host, self.port, self.f, cf)
        else:
            c = internet.TCPClient(self.host, self.port, self.f)

        c.setServiceParent(self)
