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
# Portions Copyright Buildbot Team Members
# Portions Copyright Canonical Ltd. 2009

import enum
import random
import string

from twisted.internet import defer
from twisted.python import failure
from twisted.python import log
from zope.interface import implementer

from buildbot.interfaces import ILatentMachine
from buildbot.interfaces import ILatentWorker
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.interfaces import LatentWorkerSubstantiatiationCancelled
from buildbot.util import Notifier
from buildbot.util import deferwaiter
from buildbot.worker.base import AbstractWorker


class States(enum.Enum):
    # Represents the states of AbstractLatentWorker

    NOT_SUBSTANTIATED = 0

    # When in this state, self._substantiation_notifier is waited on. The
    # notifier is notified immediately after the state transition out of
    # SUBSTANTIATING.
    SUBSTANTIATING = 1

    # This is the same as SUBSTANTIATING, the difference is that start_instance
    # has been called
    SUBSTANTIATING_STARTING = 2

    SUBSTANTIATED = 3

    # When in this state, self._start_stop_lock is held.
    INSUBSTANTIATING = 4

    # This state represents the case when insubstantiation is in progress and
    # we also request substantiation at the same time. Substantiation will be
    # started as soon as insubstantiation completes. Note, that the opposite
    # actions are not supported: insubstantiation during substantiation will
    # cancel the substantiation.
    #
    # When in this state, self._start_stop_lock is held.
    #
    # When in this state self.substantiation_build is not None.
    INSUBSTANTIATING_SUBSTANTIATING = 5

    # This state represents a worker that is shut down. Effectively, it's NOT_SUBSTANTIATED
    # plus that we will abort if anyone tries to substantiate it.
    SHUT_DOWN = 6


@implementer(ILatentWorker)
class AbstractLatentWorker(AbstractWorker):

    """A worker that will start up a worker instance when needed.

    To use, subclass and implement start_instance and stop_instance.

    Additionally, if the instances render any kind of data affecting instance
    type from the build properties, set the class variable
    builds_may_be_incompatible to True and override isCompatibleWithBuild
    method.

    See ec2.py for a concrete example.
    """

    substantiation_build = None
    build_wait_timer = None
    start_missing_on_startup = False

    # override if the latent worker may connect without substantiate. Most
    # often this will be used in workers whose lifetime is managed by
    # latent machines.
    starts_without_substantiate = False

    # Caveats: The handling of latent workers is much more complex than it
    # might seem. The code must handle at least the following conditions:
    #
    #   - non-silent disconnection by the worker at any time which generated
    #   TCP resets and in the end resulted in detached() being called
    #
    #   - silent disconnection by worker at any time by silent TCP connection
    #   failure which did not generate TCP resets, but on the other hand no
    #   response may be received. self.conn is not None is that case.
    #
    #   - no disconnection by worker during substantiation when
    #   build_wait_timeout param is negative.
    #
    #   - worker attaching before start_instance returned.
    #
    # The above means that the following parts of the state must be tracked separately and can
    # result in various state combinations:
    #   - connection state of the worker (self.conn)
    #   - intended state of the worker (self.state)
    #   - whether start_instance() has been called and has not yet finished.

    state = States.NOT_SUBSTANTIATED

    '''
    state transitions:

    substantiate(): either of
        NOT_SUBSTANTIATED -> SUBSTANTIATING
        INSUBSTANTIATING -> INSUBSTANTIATING_SUBSTANTIATING

    _substantiate():
        either of:
        SUBSTANTIATING -> SUBSTANTIATING_STARTING
        SUBSTANTIATING -> SUBSTANTIATING_STARTING -> SUBSTANTIATED

    attached():
        either of:
        SUBSTANTIATING -> SUBSTANTIATED
        SUBSTANTIATING_STARTING -> SUBSTANTIATED
        then:
        self.conn -> not None

    detached():
        self.conn -> None

    errors in any of above will call insubstantiate()

    insubstantiate():
        either of:
            SUBSTANTIATED -> INSUBSTANTIATING
            INSUBSTANTIATING_SUBSTANTIATING -> INSUBSTANTIATING (cancels substantiation request)
            SUBSTANTIATING -> INSUBSTANTIATING
            SUBSTANTIATING -> INSUBSTANTIATING_SUBSTANTIATING
            SUBSTANTIATING_STARTING -> INSUBSTANTIATING
            SUBSTANTIATING_STARTING -> INSUBSTANTIATING_SUBSTANTIATING

        then:
            < other state transitions may happen during this time >

        then either of:
            INSUBSTANTIATING_SUBSTANTIATING -> SUBSTANTIATING
            INSUBSTANTIATING -> NOT_SUBSTANTIATED

    stopService():
        NOT_SUBSTANTIATED -> SHUT_DOWN
    '''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._substantiation_notifier = Notifier()
        self._start_stop_lock = defer.DeferredLock()
        self._deferwaiter = deferwaiter.DeferWaiter()
        self._check_instance_timer = None

    def checkConfig(self, name, password,
                    build_wait_timeout=60 * 10,
                    check_instance_interval=10,
                    **kwargs):
        super().checkConfig(name, password, **kwargs)

    def reconfigService(self, name, password,
                        build_wait_timeout=60 * 10,
                        check_instance_interval=10,
                        **kwargs):
        self.build_wait_timeout = build_wait_timeout
        self.check_instance_interval = check_instance_interval
        return super().reconfigService(name, password, **kwargs)

    def _generate_random_password(self):
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(20))

    def getRandomPass(self):
        """
        Compute a random password. Latent workers are started by the master, so master can setup
        the password too. Backends should prefer to use this API as it handles edge cases.
        """

        # We should return an existing password if we're reconfiguring a substantiated worker.
        # Otherwise the worker may be rejected if its password was changed during substantiation.
        # To simplify, we only allow changing passwords for workers that aren't substantiated.
        if self.state not in [States.NOT_SUBSTANTIATED, States.SHUT_DOWN]:
            if self.password is not None:
                return self.password

            # pragma: no cover
            log.err('{}: could not reuse password of substantiated worker (password == None)',
                    repr(self))

        return self._generate_random_password()

    @property
    def building(self):
        # A LatentWorkerForBuilder will only be busy if it is building.
        return {wfb for wfb in self.workerforbuilders.values()
                if wfb.isBusy()}

    def failed_to_start(self, instance_id, instance_state):
        log.msg(f'{self.__class__.__name__} {self.workername} failed to start instance '
                f'{instance_id} ({instance_state})')
        raise LatentWorkerFailedToSubstantiate(instance_id, instance_state)

    def _log_start_stop_locked(self, action_str):
        if self._start_stop_lock.locked:
            log.msg(('while {} worker {}: waiting until previous ' +
                     'start_instance/stop_instance finishes').format(action_str, self))

    def start_instance(self, build):
        # responsible for starting instance that will try to connect with this
        # master.  Should return deferred with either True (instance started)
        # or False (instance not started, so don't run a build here).  Problems
        # should use an errback.
        raise NotImplementedError

    def stop_instance(self, fast=False):
        # responsible for shutting down instance.
        raise NotImplementedError

    def check_instance(self):
        return True

    @property
    def substantiated(self):
        return self.state == States.SUBSTANTIATED and self.conn is not None

    def substantiate(self, wfb, build):
        log.msg(f"substantiating worker {wfb}")

        if self.state == States.SHUT_DOWN:
            return defer.succeed(False)

        if self.state == States.SUBSTANTIATED and self.conn is not None:
            return defer.succeed(True)

        if self.state in [States.SUBSTANTIATING,
                          States.SUBSTANTIATING_STARTING,
                          States.INSUBSTANTIATING_SUBSTANTIATING]:
            return self._substantiation_notifier.wait()

        self.startMissingTimer()

        # if anything of the following fails synchronously we need to have a
        # deferred ready to be notified
        d = self._substantiation_notifier.wait()

        if self.state == States.SUBSTANTIATED and self.conn is None:
            # connection dropped while we were substantiated.
            # insubstantiate to clean up and then substantiate normally.
            d_ins = self.insubstantiate(force_substantiation_build=build)
            d_ins.addErrback(log.err, 'while insubstantiating')
            return d

        assert self.state in [States.NOT_SUBSTANTIATED,
                              States.INSUBSTANTIATING]

        if self.state == States.NOT_SUBSTANTIATED:
            self.state = States.SUBSTANTIATING
            self._substantiate(build)
        else:
            self.state = States.INSUBSTANTIATING_SUBSTANTIATING
            self.substantiation_build = build
        return d

    @defer.inlineCallbacks
    def _substantiate(self, build):
        assert self.state == States.SUBSTANTIATING
        try:
            # if build_wait_timeout is negative we don't ever disconnect the
            # worker ourselves, so we don't need to wait for it to attach
            # to declare it as substantiated.
            dont_wait_to_attach = \
                self.build_wait_timeout < 0 and self.conn is not None

            start_success = True
            if ILatentMachine.providedBy(self.machine):
                start_success = yield self.machine.substantiate(self)

            try:
                self._log_start_stop_locked('substantiating')
                yield self._start_stop_lock.acquire()

                if start_success:
                    self.state = States.SUBSTANTIATING_STARTING
                    start_success = yield self.start_instance(build)
            finally:
                self._start_stop_lock.release()

            if not start_success:
                # this behaviour is kept as compatibility, but it is better
                # to just errback with a workable reason
                msg = "Worker does not want to substantiate at this time"
                raise LatentWorkerFailedToSubstantiate(self.name, msg)

            if dont_wait_to_attach and \
                    self.state == States.SUBSTANTIATING_STARTING and \
                    self.conn is not None:
                log.msg(f"Worker {self.name} substantiated (already attached)")
                self.state = States.SUBSTANTIATED
                self._fireSubstantiationNotifier(True)
            else:
                self._start_check_instance_timer()

        except Exception as e:
            self.stopMissingTimer()
            self._substantiation_failed(failure.Failure(e))
            # swallow the failure as it is notified

    def _fireSubstantiationNotifier(self, result):
        if not self._substantiation_notifier:
            log.msg(f"No substantiation deferred for {self.name}")
            return

        result_msg = 'success' if result is True else 'failure'
        log.msg(f"Firing {self.name} substantiation deferred with {result_msg}")

        self._substantiation_notifier.notify(result)

    @defer.inlineCallbacks
    def attached(self, conn):
        self._stop_check_instance_timer()

        if self.state != States.SUBSTANTIATING_STARTING and \
                self.build_wait_timeout >= 0:
            msg = (f'Worker {self.name} received connection while not trying to substantiate.'
                   'Disconnecting.')
            log.msg(msg)
            self._deferwaiter.add(self._disconnect(conn))
            raise RuntimeError(msg)

        try:
            yield super().attached(conn)
        except Exception:
            self._substantiation_failed(failure.Failure())
            return
        log.msg(f"Worker {self.name} substantiated \\o/")

        # only change state when we are actually substantiating. We could
        # end up at this point in different state than SUBSTANTIATING_STARTING
        # if build_wait_timeout is negative. In that case, the worker is never
        # shut down, but it may reconnect if the connection drops on its side
        # without master seeing this condition.
        #
        # When build_wait_timeout is not negative, we throw an error (see above)
        if self.state in [States.SUBSTANTIATING,
                          States.SUBSTANTIATING_STARTING]:
            self.state = States.SUBSTANTIATED
        self._fireSubstantiationNotifier(True)

    def attachBuilder(self, builder):
        wfb = self.workerforbuilders.get(builder.name)
        return wfb.attached(self, self.worker_commands)

    def _missing_timer_fired(self):
        self.missing_timer = None
        return self._substantiation_failed(defer.TimeoutError())

    def _substantiation_failed(self, failure):
        if self.state in [States.SUBSTANTIATING,
                          States.SUBSTANTIATING_STARTING]:
            self._fireSubstantiationNotifier(failure)

        d = self.insubstantiate()
        d.addErrback(log.err, 'while insubstantiating')
        self._deferwaiter.add(d)

        # notify people, but only if we're still in the config
        if not self.parent or not self.notify_on_missing:
            return None

        return self.master.data.updates.workerMissing(
            workerid=self.workerid,
            masterid=self.master.masterid,
            last_connection="Latent worker never connected",
            notify=self.notify_on_missing
        )

    def canStartBuild(self):
        # we were disconnected, but all the builds are not yet cleaned up.
        if self.conn is None and self.building:
            return False
        return super().canStartBuild()

    def buildStarted(self, wfb):
        assert wfb.isBusy()
        self._clearBuildWaitTimer()

        if ILatentMachine.providedBy(self.machine):
            self.machine.notifyBuildStarted()

    def buildFinished(self, wfb):
        assert not wfb.isBusy()
        if not self.building:
            if self.build_wait_timeout == 0:
                # we insubstantiate asynchronously to trigger more bugs with
                # the fake reactor
                self.master.reactor.callLater(0, self._soft_disconnect)
                # insubstantiate will automatically retry to create build for
                # this worker
            else:
                self._setBuildWaitTimer()

        # AbstractWorker.buildFinished() will try to start the next build for
        # that worker
        super().buildFinished(wfb)

        if ILatentMachine.providedBy(self.machine):
            self.machine.notifyBuildFinished()

    def _clearBuildWaitTimer(self):
        if self.build_wait_timer is not None:
            if self.build_wait_timer.active():
                self.build_wait_timer.cancel()
            self.build_wait_timer = None

    def _setBuildWaitTimer(self):
        self._clearBuildWaitTimer()
        if self.build_wait_timeout <= 0:
            return
        self.build_wait_timer = self.master.reactor.callLater(
            self.build_wait_timeout, self._soft_disconnect)

    def _stop_check_instance_timer(self):
        if self._check_instance_timer is not None:
            if self._check_instance_timer.active():
                self._check_instance_timer.cancel()
            self._check_instance_timer = None

    def _start_check_instance_timer(self):
        self._stop_check_instance_timer()
        self._check_instance_timer = self.master.reactor.callLater(
            self.check_instance_interval, self._check_instance_timer_fired
        )

    def _check_instance_timer_fired(self):
        self._deferwaiter.add(self._check_instance_timer_fired_impl())

    @defer.inlineCallbacks
    def _check_instance_timer_fired_impl(self):
        self._check_instance_timer = None
        if self.state != States.SUBSTANTIATING_STARTING:
            # The only case when we want to recheck whether the instance has not failed is
            # between call to start_instance() and successful attachment of the worker.
            return

        if self._start_stop_lock.locked:  # pragma: no cover
            # This can't actually happen, because we start the timer for instance checking after
            # start_instance() completed and in insubstantiation the state is changed from
            # SUBSTANTIATING_STARTING as soon as the lock is acquired.
            return

        try:
            yield self._start_stop_lock.acquire()
            is_good = yield self.check_instance()
            if not is_good:
                yield self._substantiation_failed(
                    LatentWorkerFailedToSubstantiate(
                        self.name, 'latent worker crashed before connecting'
                    )
                )
                return
        finally:
            self._start_stop_lock.release()

        # if check passes, schedule another one until worker connects
        self._start_check_instance_timer()

    @defer.inlineCallbacks
    def insubstantiate(self, fast=False, force_substantiation_build=None):
        # If force_substantiation_build is not None, we'll try to substantiate the given build
        # after insubstantiation concludes. This parameter allows to go directly to the
        # SUBSTANTIATING state without going through NOT_SUBSTANTIATED state.

        log.msg(f"insubstantiating worker {self}")

        if self.state == States.INSUBSTANTIATING_SUBSTANTIATING:
            # there's another insubstantiation ongoing. We'll wait for it to finish by waiting
            # on self._start_stop_lock
            self.state = States.INSUBSTANTIATING
            self.substantiation_build = None
            self._fireSubstantiationNotifier(
                failure.Failure(LatentWorkerSubstantiatiationCancelled()))

        try:
            self._log_start_stop_locked('insubstantiating')
            yield self._start_stop_lock.acquire()

            assert self.state not in [States.INSUBSTANTIATING,
                                      States.INSUBSTANTIATING_SUBSTANTIATING]

            if self.state in [States.NOT_SUBSTANTIATED, States.SHUT_DOWN]:
                return

            prev_state = self.state

            if force_substantiation_build is not None:
                self.state = States.INSUBSTANTIATING_SUBSTANTIATING
                self.substantiation_build = force_substantiation_build
            else:
                self.state = States.INSUBSTANTIATING

            if prev_state in [States.SUBSTANTIATING, States.SUBSTANTIATING_STARTING]:
                self._fireSubstantiationNotifier(
                    failure.Failure(LatentWorkerSubstantiatiationCancelled()))

            self._clearBuildWaitTimer()
            self._stop_check_instance_timer()

            if prev_state in [States.SUBSTANTIATING_STARTING, States.SUBSTANTIATED]:
                try:
                    yield self.stop_instance(fast)
                except Exception as e:
                    # The case of failure for insubstantiation is bad as we have a
                    # left-over costing resource There is not much thing to do here
                    # generically, so we must put the problem of stop_instance
                    # reliability to the backend driver
                    log.err(e, "while insubstantiating")

            assert self.state in [States.INSUBSTANTIATING,
                                  States.INSUBSTANTIATING_SUBSTANTIATING]

            if self.state == States.INSUBSTANTIATING_SUBSTANTIATING:
                build, self.substantiation_build = self.substantiation_build, None
                self.state = States.SUBSTANTIATING
                self._substantiate(build)
            else:  # self.state == States.INSUBSTANTIATING:
                self.state = States.NOT_SUBSTANTIATED

        finally:
            self._start_stop_lock.release()

        self.botmaster.maybeStartBuildsForWorker(self.name)

    @defer.inlineCallbacks
    def _soft_disconnect(self, fast=False, stopping_service=False):
        # a negative build_wait_timeout means the worker should never be shut
        # down, so just disconnect.
        if not stopping_service and self.build_wait_timeout < 0:
            yield super().disconnect()
            return

        self.stopMissingTimer()

        # we add the Deferreds to DeferWaiter because we don't wait for a Deferred if
        # the other Deferred errbacks
        yield defer.DeferredList([
            self._deferwaiter.add(super().disconnect()),
            self._deferwaiter.add(self.insubstantiate(fast))
        ], consumeErrors=True, fireOnOneErrback=True)

    def disconnect(self):
        self._deferwaiter.add(self._soft_disconnect())
        # this removes the worker from all builders.  It won't come back
        # without a restart (or maybe a sighup)
        self.botmaster.workerLost(self)

    @defer.inlineCallbacks
    def stopService(self):
        # stops the service. Waits for any pending substantiations, insubstantiations or builds
        # that are running or about to start to complete.
        while self.state not in [States.NOT_SUBSTANTIATED, States.SHUT_DOWN]:
            if self.state in [States.INSUBSTANTIATING,
                              States.INSUBSTANTIATING_SUBSTANTIATING,
                              States.SUBSTANTIATING,
                              States.SUBSTANTIATING_STARTING]:
                self._log_start_stop_locked('stopService')
                yield self._start_stop_lock.acquire()
                self._start_stop_lock.release()

            if self.conn is not None or self.state in [States.SUBSTANTIATED,
                                                       States.SUBSTANTIATING_STARTING]:
                yield self._soft_disconnect(stopping_service=True)

            yield self._deferwaiter.wait()

        # prevent any race conditions with any future builds that are in the process of
        # being started.
        if self.state == States.NOT_SUBSTANTIATED:
            self.state = States.SHUT_DOWN

        self._clearBuildWaitTimer()
        self._stop_check_instance_timer()
        res = yield super().stopService()
        return res

    def updateWorker(self):
        """Called to add or remove builders after the worker has connected.

        Also called after botmaster's builders are initially set.

        @return: a Deferred that indicates when an attached worker has
        accepted the new builders and/or released the old ones."""
        for b in self.botmaster.getBuildersForWorker(self.name):
            if b.name not in self.workerforbuilders:
                b.addLatentWorker(self)
        return super().updateWorker()


class LocalLatentWorker(AbstractLatentWorker):
    """
    A worker that can be suspended by shutting down or suspending the hardware
    it runs on. It is intended to be used with LatentMachines.
    """
    starts_without_substantiate = True

    def checkConfig(self, name, password, **kwargs):
        super().checkConfig(self, name, password, build_wait_timeout=-1,
                            **kwargs)

    def reconfigService(self, name, password, **kwargs):
        return super().reconfigService(name, password, build_wait_timeout=-1,
                                       **kwargs)
