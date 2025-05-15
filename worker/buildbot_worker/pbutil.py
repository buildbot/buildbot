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


"""Base classes handy for use with PB clients."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import NoReturn
from typing import cast

from twisted.application.internet import backoffPolicy
from twisted.cred import error
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.spread import pb
from twisted.spread.pb import PBClientFactory

from buildbot_worker.compat import bytes2unicode

if TYPE_CHECKING:
    from twisted.cred.credentials import UsernamePassword
    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorCore
    from twisted.internet.interfaces import IReactorTime
    from twisted.python.failure import Failure
    from twisted.spread.pb import Broker
    from twisted.spread.pb import RemoteReference

    from buildbot_worker.pb import BotPb
    from buildbot_worker.util.twisted import InlineCallbacksType


class AutoLoginPBFactory(PBClientFactory):
    """Factory for PB brokers that are managed through a ClientService.

    Upon reconnect issued by ClientService this factory will re-login.

    Instead of using f.getRootObject (which gives a Deferred that can only
    be fired once), override the gotRootObject method. GR -> yes in case a user
    would use that to be notified of root object appearances, it wouldn't
    work. But getRootObject() can itself be used as much as one wants.

    Instead of using the f.login (which is also one-shot), call
    f.startLogin() with the credentials and client, and override the
    gotPerspective method.

    gotRootObject and gotPerspective will be called each time the object is
    received (once per successful connection attempt).

    If an authorization error occurs, failedToGetPerspective() will be
    invoked.
    """

    def __init__(  # pylint: disable=wrong-spelling-in-docstring
        self,
        retryPolicy: Callable[[int], float] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        @param retryPolicy: A policy configuring how long L{AutoLoginPBFactory} will
            wait between attempts to connect to C{endpoint}.
        @type retryPolicy: callable taking (the number of failed connection
            attempts made in a row (L{int})) and returning the number of
            seconds to wait before making another attempt.
        """
        PBClientFactory.__init__(self, **kwargs)
        self._timeoutForAttempt = backoffPolicy() if retryPolicy is None else retryPolicy
        self._failedAttempts = 0
        self._login_d: Deferred | None = None

    def clientConnectionMade(self, broker: Broker, retryPolicy: None = None) -> None:
        PBClientFactory.clientConnectionMade(self, broker)
        self._login_d = self.doLogin(self._root, broker)
        self.gotRootObject(self._root)

    def login(self, *args: Any) -> NoReturn:
        raise RuntimeError("login is one-shot: use startLogin instead")

    def startLogin(self, credentials: UsernamePassword, client: BotPb | None = None) -> None:
        self._credentials = credentials
        self._client = client

    def doLogin(self, root: RemoteReference, broker: Broker) -> Deferred:
        d = self._cbSendUsername(
            root, self._credentials.username, self._credentials.password, self._client
        )
        d.addCallbacks(self.gotPerspective, self.failedToGetPerspective, errbackArgs=(broker,))
        return d

    def stopFactory(self) -> None:
        if self._login_d:
            self._login_d.cancel()
        PBClientFactory.stopFactory(self)

    # methods to override

    def gotPerspective(self, perspective: RemoteReference) -> None:
        """The remote avatar or perspective (obtained each time this factory
        connects) is now available."""

    def gotRootObject(self, root: RemoteReference) -> None:
        """The remote root object (obtained each time this factory connects)
        is now available. This method will be called each time the connection
        is established and the object reference is retrieved."""

    @defer.inlineCallbacks
    def failedToGetPerspective(self, why: Failure, broker: Broker) -> InlineCallbacksType[None]:
        """The login process failed, most likely because of an authorization
        failure (bad password), but it is also possible that we lost the new
        connection before we managed to send our credentials.
        """
        log.msg("ReconnectingPBClientFactory.failedToGetPerspective")
        # put something useful in the logs
        if why.check(pb.PBConnectionLost):
            log.msg("we lost the brand-new connection")
            # fall through
        elif why.check(error.UnauthorizedLogin):
            log.msg("unauthorized login; check worker name and password")
            # fall through
        else:
            log.err(why, 'While trying to connect:')
            cast("IReactorCore", reactor).stop()
            return

        self._failedAttempts += 1
        delay = self._timeoutForAttempt(self._failedAttempts)
        log.msg(f"Scheduling retry {self._failedAttempts} to getPerspective in {delay} seconds.")

        # Delay the retry according to the backoff policy
        try:
            yield task.deferLater(cast("IReactorTime", reactor), delay, lambda: None)
        except defer.CancelledError:
            pass

        # lose the current connection, which will trigger a retry
        assert broker.transport is not None
        broker.transport.loseConnection()


def decode(data: Any, encoding: str = 'utf-8', errors: str = 'strict') -> Any:
    """We need to convert a dictionary where keys and values
    are bytes, to unicode strings.  This happens when a
    Python 2 master sends a dictionary back to a Python 3 worker.
    """
    if isinstance(data, bytes):
        return bytes2unicode(data, encoding, errors)
    if isinstance(data, dict):
        return type(data)(map(decode, data.items()))
    if isinstance(data, (list, tuple)):
        return type(data)(map(decode, data))
    return data
