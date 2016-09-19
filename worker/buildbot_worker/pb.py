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

import os.path
import signal

from twisted.application import service
from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.internet.endpoints import clientFromString
from twisted.python import log
from twisted.spread import pb

from buildbot_worker.base import BotBase
from buildbot_worker.base import WorkerBase
from buildbot_worker.base import WorkerForBuilderBase
from buildbot_worker.pbutil import AutoLoginPBFactory

from .backports import ClientService


class UnknownCommand(pb.Error):
    pass


class WorkerForBuilderPb(WorkerForBuilderBase, pb.Referenceable):
    pass


class BotPb(BotBase, pb.Referenceable):
    WorkerForBuilder = WorkerForBuilderPb


class BotFactory(AutoLoginPBFactory):
    """The protocol factory for the worker.

    buildmaster host, port and maxDelay are accepted for backwards
    compatibility only.

    With endpoints, everything related to reconnection is managed by the
    service.

    buildmaster_host and port were used for logging only, mostly within
    reconnection methods

    maxDelay is a feature of protocol.ReconnectingClientFactory, that we
    don't use anymore. With endpoints, this is managed by the service
    (TODO reimplement that)

    This class implements the optional applicative keepalives, on top of
    AutoLoginPBFactory.

    'keepaliveInterval' serves two purposes. The first is to keep the
    connection alive: it guarantees that there will be at least some
    traffic once every 'keepaliveInterval' seconds, which may help keep an
    interposed NAT gateway from dropping the address mapping because it
    thinks the connection has been abandoned.  This also gives the operating
    system a chance to notice that the master has gone away, and inform us
    of such (although this could take several minutes).

    @ivar currentKeepAliveWaiter: either ``None`` or a deferred for the reply
                                  to the keepalive (mostly useful for tests)
    """
    keepaliveInterval = None  # None = do not use keepalives
    currentKeepaliveWaiter = None
    keepaliveTimer = None
    unsafeTracebacks = 1
    perspective = None

    # for tests
    _reactor = reactor

    def __init__(self, buildmaster_host, port, keepaliveInterval, maxDelay):
        AutoLoginPBFactory.__init__(self)
        self.keepaliveInterval = keepaliveInterval

    def gotPerspective(self, perspective):
        log.msg("Connected to buildmaster; worker is ready")
        AutoLoginPBFactory.gotPerspective(self, perspective)
        self.perspective = perspective
        try:
            perspective.broker.transport.setTcpKeepAlive(1)
        except Exception:
            log.msg("unable to set SO_KEEPALIVE")
            if not self.keepaliveInterval:
                self.keepaliveInterval = 10 * 60
        self.activity()
        if self.keepaliveInterval:
            log.msg("sending application-level keepalives every %d seconds"
                    % self.keepaliveInterval)
            self.startTimers()

    def startTimers(self):
        assert self.keepaliveInterval
        assert not self.keepaliveTimer

        def doKeepalive():
            self.keepaliveTimer = None
            self.startTimers()

            # Send the keepalive request.  If an error occurs
            # was already dropped, so just log and ignore.
            log.msg("sending app-level keepalive")
            d = self.perspective.callRemote("keepalive")
            self.currentKeepaliveWaiter = defer.Deferred()

            def keepaliveReplied(details):
                log.msg("Master replied to keepalive, everything's fine")
                self.currentKeepaliveWaiter.callback(details)
                self.currentKeepaliveWaiter = None
                return details

            d.addCallback(keepaliveReplied)
            d.addErrback(log.err, "error sending keepalive")
        self.keepaliveTimer = self._reactor.callLater(self.keepaliveInterval,
                                                      doKeepalive)

    def stopTimers(self):
        if self.keepaliveTimer:
            self.keepaliveTimer.cancel()
            self.keepaliveTimer = None

    def activity(self, res=None):
        """Subclass or monkey-patch this method to be alerted whenever there is
        active communication between the master and worker."""
        pass

    def stopFactory(self):
        self.stopTimers()
        AutoLoginPBFactory.stopFactory(self)


class Worker(WorkerBase, service.MultiService):
    """The service class to be instantiated from buildbot.tac

    to just pass a connection description string, set buildmaster_host and
    port to None, and use conndescr.

    note: keepaliveTimeout is ignored, but preserved here for
    backward-compatibility
    """
    Bot = BotPb

    def __init__(self, buildmaster_host, port, name, passwd, basedir,
                 keepalive, usePTY=None, keepaliveTimeout=None, umask=None,
                 maxdelay=300, numcpus=None, unicode_encoding=None,
                 allow_shutdown=None, conndescr=None):

        assert usePTY is None, "worker-side usePTY is not supported anymore"
        assert (conndescr is None or
                (buildmaster_host, port) == (None, None)), (
                    "If you want to supply a connection description string, "
                    "then set host and port to None")

        service.MultiService.__init__(self)
        WorkerBase.__init__(
            self, name, basedir, umask=umask, unicode_encoding=unicode_encoding)
        if keepalive == 0:
            keepalive = None

        self.numcpus = numcpus
        self.shutdown_loop = None

        if allow_shutdown == 'signal':
            if not hasattr(signal, 'SIGHUP'):
                raise ValueError("Can't install signal handler")
        elif allow_shutdown == 'file':
            self.shutdown_file = os.path.join(basedir, 'shutdown.stamp')
            self.shutdown_mtime = 0

        self.allow_shutdown = allow_shutdown
        bf = self.bf = BotFactory(buildmaster_host, port, keepalive, maxdelay)
        bf.startLogin(
            credentials.UsernamePassword(name, passwd), client=self.bot)
        if conndescr is None:
            conndescr = self.tcpConnectionDescr(buildmaster_host, port)
        self.conndescr = conndescr  # for log messages and unit tests
        endpoint = clientFromString(reactor, conndescr)
        pb_service = ClientService(endpoint, bf)
        self.addService(pb_service)

    @staticmethod
    def tcpConnectionDescr(host, port):
        """Build a simple TCP connection description from host and port.

        Takes care of escaping the two separators in connection description
        syntax: colon and equal sign.

        Colons appear notably in IPv6 addresses; while the equal sign is not
        allowed in DNS, nor any current IP addresses, it can be valid in
        ``/etc/hosts`` entries.
        """
        return 'tcp:host={0}:port={1}'.format(
            host.replace(':', r'\:').replace('=', r'\='),
            port)

    def startService(self):
        WorkerBase.startService(self)

        if self.allow_shutdown == 'signal':
            log.msg("Setting up SIGHUP handler to initiate shutdown")
            signal.signal(signal.SIGHUP, self._handleSIGHUP)
        elif self.allow_shutdown == 'file':
            log.msg("Watching %s's mtime to initiate shutdown" %
                    self.shutdown_file)
            if os.path.exists(self.shutdown_file):
                self.shutdown_mtime = os.path.getmtime(self.shutdown_file)
            self.shutdown_loop = l = task.LoopingCall(self._checkShutdownFile)
            l.start(interval=10)

    def stopService(self):
        if self.shutdown_loop:
            self.shutdown_loop.stop()
            self.shutdown_loop = None
        return service.MultiService.stopService(self)

    def _handleSIGHUP(self, *args):
        log.msg("Initiating shutdown because we got SIGHUP")
        return self.gracefulShutdown()

    def _checkShutdownFile(self):
        if os.path.exists(self.shutdown_file) and \
                os.path.getmtime(self.shutdown_file) > self.shutdown_mtime:
            log.msg("Initiating shutdown because %s was touched" %
                    self.shutdown_file)
            self.gracefulShutdown()

            # In case the shutdown fails, update our mtime so we don't keep
            # trying to shutdown over and over again.
            # We do want to be able to try again later if the master is
            # restarted, so we'll keep monitoring the mtime.
            self.shutdown_mtime = os.path.getmtime(self.shutdown_file)

    def gracefulShutdown(self):
        """Start shutting down"""
        if not self.bf.perspective:
            log.msg("No active connection, shutting down NOW")
            reactor.stop()
            return

        log.msg(
            "Telling the master we want to shutdown after any running builds are finished")
        d = self.bf.perspective.callRemote("shutdown")

        def _shutdownfailed(err):
            if err.check(AttributeError):
                log.msg(
                    "Master does not support worker initiated shutdown.  Upgrade master to 0.8.3 or later to use this feature.")
            else:
                log.msg('callRemote("shutdown") failed')
                log.err(err)

        d.addErrback(_shutdownfailed)
        return d
