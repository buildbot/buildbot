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

import os.path
import signal

from twisted.application import service
from twisted.application.internet import ClientService
from twisted.application.internet import backoffPolicy
from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.internet.endpoints import clientFromString
from twisted.python import log
from twisted.spread import pb

from buildbot_worker import util
from buildbot_worker.base import BotBase
from buildbot_worker.base import WorkerBase
from buildbot_worker.base import WorkerForBuilderBase
from buildbot_worker.compat import unicode2bytes
from buildbot_worker.pbutil import AutoLoginPBFactory


class UnknownCommand(pb.Error):
    pass


class WorkerForBuilderPb(WorkerForBuilderBase, pb.Referenceable):
    pass


class BotPb(BotBase, pb.Referenceable):
    WorkerForBuilder = WorkerForBuilderPb


class BotFactory(AutoLoginPBFactory):
    """The protocol factory for the worker.

    This class implements the optional applicative keepalives, on top of
    AutoLoginPBFactory.

    'keepaliveInterval' serves two purposes. The first is to keep the
    connection alive: it guarantees that there will be at least some
    traffic once every 'keepaliveInterval' seconds, which may help keep an
    interposed NAT gateway from dropping the address mapping because it
    thinks the connection has been abandoned.  This also gives the operating
    system a chance to notice that the master has gone away, and inform us
    of such (although this could take several minutes).

    buildmaster host, port and maxDelay are accepted for backwards
    compatibility only.
    """
    keepaliveInterval = None  # None = do not use keepalives
    keepaliveTimer = None
    perspective = None

    _reactor = reactor

    def __init__(self, buildmaster_host, port, keepaliveInterval, maxDelay):
        AutoLoginPBFactory.__init__(self)
        self.keepaliveInterval = keepaliveInterval
        self.keepalive_lock = defer.DeferredLock()
        self._shutting_down = False

        # notified when shutdown is complete.
        self._shutdown_notifier = util.Notifier()
        self._active_keepalives = 0

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
            log.msg("sending application-level keepalives every {0} seconds".format(
                    self.keepaliveInterval))
            self.startTimers()

    def startTimers(self):
        assert self.keepaliveInterval
        assert not self.keepaliveTimer

        @defer.inlineCallbacks
        def doKeepalive():
            self._active_keepalives += 1
            self.keepaliveTimer = None
            self.startTimers()

            yield self.keepalive_lock.acquire()
            self.currentKeepaliveWaiter = defer.Deferred()

            # Send the keepalive request.  If an error occurs
            # was already dropped, so just log and ignore.
            log.msg("sending app-level keepalive")
            try:
                details = yield self.perspective.callRemote("keepalive")
                log.msg("Master replied to keepalive, everything's fine")
                self.currentKeepaliveWaiter.callback(details)
                self.currentKeepaliveWaiter = None
            except (pb.PBConnectionLost, pb.DeadReferenceError):
                log.msg("connection already shut down when attempting keepalive")
            except Exception as e:
                log.err(e, "error sending keepalive")
            finally:
                self.keepalive_lock.release()
                self._active_keepalives -= 1
                self._checkNotifyShutdown()

        self.keepaliveTimer = self._reactor.callLater(self.keepaliveInterval,
                                                      doKeepalive)

    def _checkNotifyShutdown(self):
        if self._active_keepalives == 0 and self._shutting_down and \
                self._shutdown_notifier is not None:
            self._shutdown_notifier.notify(None)
            self._shutdown_notifier = None

    def stopTimers(self):
        self._shutting_down = True

        if self.keepaliveTimer:
            # by cancelling the timer we are guaranteed that doKeepalive() won't be called again,
            # as there's no interruption point between doKeepalive() beginning and call to
            # startTimers()
            self.keepaliveTimer.cancel()
            self.keepaliveTimer = None

        self._checkNotifyShutdown()

    def activity(self, res=None):
        """Subclass or monkey-patch this method to be alerted whenever there is
        active communication between the master and worker."""

    def stopFactory(self):
        self.stopTimers()
        AutoLoginPBFactory.stopFactory(self)

    @defer.inlineCallbacks
    def waitForCompleteShutdown(self):
        # This function waits for a complete shutdown to happen. It's fired when all keepalives
        # have been finished and there are no pending ones.
        if self._shutdown_notifier is not None:
            yield self._shutdown_notifier.wait()


class Worker(WorkerBase, service.MultiService):
    """The service class to be instantiated from buildbot.tac

    to just pass a connection string, set buildmaster_host and
    port to None, and use connection_string.

    maxdelay is deprecated in favor of using twisted's backoffPolicy.
    """
    Bot = BotPb

    def __init__(self, buildmaster_host, port, name, passwd, basedir,
                 keepalive, usePTY=None, keepaliveTimeout=None, umask=None,
                 maxdelay=None, numcpus=None, unicode_encoding=None, useTls=None,
                 allow_shutdown=None, maxRetries=None, connection_string=None):

        assert usePTY is None, "worker-side usePTY is not supported anymore"
        assert (connection_string is None or
                (buildmaster_host, port) == (None, None)), (
                    "If you want to supply a connection string, "
                    "then set host and port to None")

        service.MultiService.__init__(self)
        WorkerBase.__init__(
            self, name, basedir, umask=umask, unicode_encoding=unicode_encoding)
        if keepalive == 0:
            keepalive = None

        name = unicode2bytes(name, self.bot.unicode_encoding)
        passwd = unicode2bytes(passwd, self.bot.unicode_encoding)

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
        if connection_string is None:
            if useTls:
                connection_type = 'tls'
            else:
                connection_type = 'tcp'

            connection_string = '{}:host={}:port={}'.format(
                connection_type,
                buildmaster_host.replace(':', r'\:'),  # escape ipv6 addresses
                port)
        endpoint = clientFromString(reactor, connection_string)

        def policy(attempt):
            if maxRetries and attempt >= maxRetries:
                reactor.stop()
            return backoffPolicy()(attempt)
        pb_service = ClientService(endpoint, bf,
                                   retryPolicy=policy)
        self.addService(pb_service)

    def startService(self):
        WorkerBase.startService(self)

        if self.allow_shutdown == 'signal':
            log.msg("Setting up SIGHUP handler to initiate shutdown")
            signal.signal(signal.SIGHUP, self._handleSIGHUP)
        elif self.allow_shutdown == 'file':
            log.msg("Watching {0}'s mtime to initiate shutdown".format(
                    self.shutdown_file))
            if os.path.exists(self.shutdown_file):
                self.shutdown_mtime = os.path.getmtime(self.shutdown_file)
            self.shutdown_loop = loop = task.LoopingCall(self._checkShutdownFile)
            loop.start(interval=10)

    @defer.inlineCallbacks
    def stopService(self):
        if self.shutdown_loop:
            self.shutdown_loop.stop()
            self.shutdown_loop = None
        yield service.MultiService.stopService(self)
        yield self.bf.waitForCompleteShutdown()

    def _handleSIGHUP(self, *args):
        log.msg("Initiating shutdown because we got SIGHUP")
        return self.gracefulShutdown()

    def _checkShutdownFile(self):
        if os.path.exists(self.shutdown_file) and \
                os.path.getmtime(self.shutdown_file) > self.shutdown_mtime:
            log.msg("Initiating shutdown because {0} was touched".format(
                    self.shutdown_file))
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
