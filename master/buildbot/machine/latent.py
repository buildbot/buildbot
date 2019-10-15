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


import enum

from twisted.internet import defer
from twisted.python import log
from zope.interface import implementer

from buildbot import interfaces
from buildbot.machine.base import Machine
from buildbot.util import Notifier


class States(enum.Enum):
    # Represents the state of LatentMachine
    STOPPED = 0
    STARTING = 1
    STARTED = 2
    STOPPING = 3


@implementer(interfaces.ILatentMachine)
class AbstractLatentMachine(Machine):

    DEFAULT_MISSING_TIMEOUT = 20 * 60

    def checkConfig(self, name,
                    build_wait_timeout=0,
                    missing_timeout=DEFAULT_MISSING_TIMEOUT, **kwargs):
        super().checkConfig(name, **kwargs)
        self.state = States.STOPPED
        self.latent_workers = []

    def reconfigService(self, name,
                        build_wait_timeout=0,
                        missing_timeout=DEFAULT_MISSING_TIMEOUT, **kwargs):
        super().reconfigService(name, **kwargs)
        self.build_wait_timeout = build_wait_timeout
        self.missing_timeout = missing_timeout

        for worker in self.workers:
            if not interfaces.ILatentWorker.providedBy(worker):
                raise Exception('Worker is not latent {}'.format(
                    worker.name))

        self.state = States.STOPPED
        self._start_notifier = Notifier()
        self._stop_notifier = Notifier()
        self._build_wait_timer = None
        self._missing_timer = None

    def start_machine(self):
        # Responsible for starting the machine. The function should return a
        # deferred which should result in True if the startup has been
        # successful, or False otherwise.
        raise NotImplementedError

    def stop_machine(self):
        # Responsible for shutting down the machine
        raise NotImplementedError

    @defer.inlineCallbacks
    def substantiate(self, starting_worker):
        if self.state == States.STOPPING:
            # wait until stop action finishes
            yield self._stop_notifier.wait()

        if self.state == States.STARTED:
            # may happen if we waited for stop to complete and in the mean
            # time the machine was successfully woken.
            return True

        # wait for already proceeding startup to finish, if any
        if self.state == States.STARTING:
            return (yield self._start_notifier.wait())

        self.state = States.STARTING

        # substantiate all workers that will start if we wake the machine. We
        # do so before waking the machine to guarantee that we're already
        # waiting for worker connection as waking may take time confirming
        # machine came online. We'll call substantiate on the worker that
        # invoked this function again, but that's okay as that function is
        # reentrant. Note that we substantiate without gathering results
        # because the original call to substantiate will get them anyway and
        # we don't want to be slowed down by other workers on the machine.
        for worker in self.workers:
            if worker.starts_without_substantiate:
                worker.substantiate(None, None)

        # Start the machine. We don't need to wait for any workers to actually
        # come online as that's handled in their substantiate() functions.
        try:
            ret = yield self.start_machine()
        except Exception as e:
            log.err(e, 'while starting latent machine {0}'.format(self.name))
            ret = False

        if not ret:
            yield defer.DeferredList([worker.insubstantiate()
                                      for worker in self.workers],
                                     consumeErrors=True)
        else:
            self._setMissingTimer()

        self.state = States.STARTED if ret else States.STOPPED
        self._start_notifier.notify(ret)

        return ret

    @defer.inlineCallbacks
    def _stop(self):
        if any(worker.building for worker in self.workers) or \
                self.state == States.STARTING:
            return None

        if self.state == States.STOPPING:
            yield self._stop_notifier.wait()
            return None

        self.state = States.STOPPING

        # wait until workers insubstantiate, then stop
        yield defer.DeferredList([worker.insubstantiate()
                                  for worker in self.workers],
                                 consumeErrors=True)
        try:
            yield self.stop_machine()
        except Exception as e:
            log.err(e, 'while stopping latent machine {0}'.format(
                self.name))

        self.state = States.STOPPED
        self._stop_notifier.notify(None)

    def notifyBuildStarted(self):
        self._clearMissingTimer()

    def notifyBuildFinished(self):
        if any(worker.building for worker in self.workers):
            self._clearBuildWaitTimer()
        else:
            self._setBuildWaitTimer()

    def _clearMissingTimer(self):
        if self._missing_timer is not None:
            if self._missing_timer.active():
                self._missing_timer.cancel()
            self._missing_timer = None

    def _setMissingTimer(self):
        self._clearMissingTimer()
        self._missing_timer = self.master.reactor.callLater(
            self.missing_timeout, self._stop)

    def _clearBuildWaitTimer(self):
        if self._build_wait_timer is not None:
            if self._build_wait_timer.active():
                self._build_wait_timer.cancel()
            self._build_wait_timer = None

    def _setBuildWaitTimer(self):
        self._clearBuildWaitTimer()
        self._build_wait_timer = self.master.reactor.callLater(
            self.build_wait_timeout, self._stop)

    def __repr__(self):
        return "<AbstractLatentMachine '{}' at {}>".format(self.name, id(self))
