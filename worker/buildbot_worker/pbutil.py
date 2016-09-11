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

from twisted.cred import error
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb
from twisted.spread.pb import PBClientFactory

from buildbot_worker.compat import bytes2unicode


class AutoLoginPBFactory(PBClientFactory):
    """Factory for PB brokers that are managed through a ClientService.

    The methods inherited from ClientFactory through PBClientFactory aren't
    called by ClientService, so there's no point inheriting them. Some of
    them are worth calling from here, though, to limit code duplication.

    Like PBClientFactory, but if the connection fails or is lost, the factory
    will attempt to reconnect.

    GR these two paragraphs below are instructions for users, not description
    of what happens.

    Instead of using f.getRootObject (which gives a Deferred that can only
    be fired once), override the gotRootObject method. GR -> yes in case a user
    would use that to be notified of root object appearances, it wouldn't
    work. But getRootObject() can itself be used as much as one wants.


    Instead of using the newcred f.login (which is also one-shot), call
    f.startLogin() with the credentials and client, and override the
    gotPerspective method.

    gotRootObject and gotPerspective will be called each time the object is
    received (once per successful connection attempt). You will probably want
    to use obj.notifyOnDisconnect to find out when the connection is lost.

    If an authorization error occurs, failedToGetPerspective() will be
    invoked.

    To use me, subclass, use in a ClientService, with ``onConnection`` added as
    ``whenConnected()`` callback

    More GR notes:
    - whenConnected() is fired upon connection *before* banana protocol neg
      so that basically, login() ends with:
         " The client selected a protocol the server didn't "
         "suggest and doesn't know: disconnecting."
    - whenConnected() is useless for behaviour upon reconnection, re-registering
      again on an active connection results in a immediate call
    - also pb is reentrant wrt the factory, and really expects it to be a
      ClientFactory, in that upon dialect selection, banana calls
      self.connectionReady(), which in turn in case of the pb protocol will
      call the factory's clientConnectionMade(). Using pb with a plain factory
      is therefore not that meaningful.

      All this together suggests to keep the changes minimal.
    """

    # hung connections wait for a relatively long time, since a busy master may
    # take a while to get back to us.
    hungConnectionTimer = None
    HUNG_CONNECTION_TIMEOUT = 120

    def clientConnectionMade(self, broker):
        PBClientFactory.clientConnectionMade(self, broker)
        self.doLogin(self._root, broker)
        self.gotRootObject(self._root)

    def buildProtocol(self, addr):
        return PBClientFactory.buildProtocol(self, addr)

    # newcred methods

    def login(self, *args):
        raise RuntimeError("login is one-shot: use startLogin instead")

    def startLogin(self, credentials, client=None):
        self._credentials = credentials
        self._client = client

    def doLogin(self, root, broker):
        # newcred login()
        d = self._cbSendUsername(root, self._credentials.username,
                                 self._credentials.password, self._client)
        d.addCallbacks(self.gotPerspective, self.failedToGetPerspective,
                       errbackArgs=(broker,))
        return d

    # methods to override

    def gotPerspective(self, perspective):
        """The remote avatar or perspective (obtained each time this factory
        connects) is now available."""

    def gotRootObject(self, root):
        """The remote root object (obtained each time this factory connects)
        is now available. This method will be called each time the connection
        is established and the object reference is retrieved."""

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
            return

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
