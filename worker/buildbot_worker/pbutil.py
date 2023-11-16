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


"""Base classes handy for use with PB clients.
"""

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems

from twisted.application.internet import backoffPolicy
from twisted.cred import error
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.spread import pb
from twisted.spread.pb import PBClientFactory

from buildbot_worker.compat import bytes2unicode


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
        self, retryPolicy=None, **kwargs
    ):
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
        self._login_d = None

    def clientConnectionMade(self, broker, retryPolicy=None):
        PBClientFactory.clientConnectionMade(self, broker)
        self._login_d = self.doLogin(self._root, broker)
        self.gotRootObject(self._root)

    def login(self, *args):
        raise RuntimeError("login is one-shot: use startLogin instead")

    def startLogin(self, credentials, client=None):
        self._credentials = credentials
        self._client = client

    def doLogin(self, root, broker):
        d = self._cbSendUsername(root, self._credentials.username,
                                 self._credentials.password, self._client)
        d.addCallbacks(self.gotPerspective, self.failedToGetPerspective,
                       errbackArgs=(broker,))
        return d

    def stopFactory(self):
        if self._login_d:
            self._login_d.cancel()
        PBClientFactory.stopFactory(self)

    # methods to override

    def gotPerspective(self, perspective):
        """The remote avatar or perspective (obtained each time this factory
        connects) is now available."""

    def gotRootObject(self, root):
        """The remote root object (obtained each time this factory connects)
        is now available. This method will be called each time the connection
        is established and the object reference is retrieved."""

    @defer.inlineCallbacks
    def failedToGetPerspective(self, why, broker):
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
            reactor.stop()
            defer.returnValue(None)

        self._failedAttempts += 1
        delay = self._timeoutForAttempt(self._failedAttempts)
        log.msg(
            "Scheduling retry {attempt} to getPerspective in {delay} seconds.".format(
                attempt=self._failedAttempts,
                delay=delay,
            )
        )

        # Delay the retry according to the backoff policy
        try:
            yield task.deferLater(reactor, delay, lambda: None)
        except defer.CancelledError:
            pass

        # lose the current connection, which will trigger a retry
        broker.transport.loseConnection()


def decode(data, encoding='utf-8', errors='strict'):
    """We need to convert a dictionary where keys and values
    are bytes, to unicode strings.  This happens when a
    Python 2 master sends a dictionary back to a Python 3 worker.
    """
    data_type = type(data)

    if data_type == bytes:
        return bytes2unicode(data, encoding, errors)
    if data_type in (dict, list, tuple):
        if data_type == dict:
            data = iteritems(data)
        return data_type(map(decode, data))
    return data
