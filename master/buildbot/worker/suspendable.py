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

import os
import stat

from twisted.internet import defer
from twisted.internet import utils
from twisted.python import log
from zope.interface import implementer

from buildbot import config
from buildbot import interfaces
from buildbot.util import Notifier
from buildbot.util import misc
from buildbot.util import private_tempdir
from buildbot.util import service
from buildbot.util.git import getSshArgsForKeys
from buildbot.util.git import getSshKnownHostsContents
from buildbot.worker import AbstractWorker
from buildbot.worker.latent import AbstractLatentWorker


@implementer(interfaces.ISuspendableWorker)
class SuspendableWorker(AbstractLatentWorker):

    def checkConfig(self, name, password, **kwargs):
        self.machine_manager = None
        AbstractLatentWorker.checkConfig(self, name, password,
                                         build_wait_timeout=-1,
                                         **kwargs)

    def reconfigService(self, name, password, **kwargs):
        return AbstractLatentWorker.reconfigService(self, name, password,
                                                    build_wait_timeout=-1,
                                                    **kwargs)

    @defer.inlineCallbacks
    def start_instance(self, build):
        if not self.machine_manager:
            log.err(('SuspendableWorker {} does not have a manager and could '
                     'not start build').format(self.name))
            ret = False
        else:
            ret = yield self.machine_manager.start_instance(self)
        defer.returnValue(ret)

    def stop_instance(self, fast=False):
        return defer.succeed(None)

    def buildStarted(self, wfb):
        AbstractLatentWorker.buildStarted(self, wfb)
        if self.machine_manager:
            self.machine_manager.notifyBuildStarted()

    def buildFinished(self, wfb):
        AbstractLatentWorker.buildFinished(self, wfb)
        if self.machine_manager:
            self.machine_manager.notifyBuildFinished()


class SuspendableMachineManager(service.BuildbotServiceManager):
    reconfig_priority = AbstractWorker.reconfig_priority - 1
    name = 'SuspendableMachineManager'
    managed_services_name = 'suspendable_machines'
    config_attr = 'suspendable_machines'


class _LocalMachineActionMixin(object):
    def setupLocal(self, command):
        if not isinstance(command, list):
            config.error('command parameter must be a list')
        self._command = command

    @defer.inlineCallbacks
    def execute(self, manager):
        args = yield manager.renderSecrets(self._command)
        _, _, code = yield utils.getProcessOutputAndValue(args[0], args[1:])
        defer.returnValue(code == 0)


class _SshActionMixin(object):
    def setupSsh(self, sshBin, host, remoteCommand, sshKey=None,
                 sshHostKey=None):
        if not isinstance(sshBin, str):
            config.error('sshBin parameter must be a string')
        if not isinstance(host, str):
            config.error('host parameter must be a string')
        if not isinstance(remoteCommand, list):
            config.error('remoteCommand parameter must be a list')

        self._sshBin = sshBin
        self._host = host
        self._remoteCommand = remoteCommand
        self._sshKey = sshKey
        self._sshHostKey = sshHostKey

    @defer.inlineCallbacks
    def _executeImpl(self, manager, key_path, known_hosts_path):
        args = getSshArgsForKeys(key_path, known_hosts_path)
        args.append((yield manager.renderSecrets(self._host)))
        args.extend((yield manager.renderSecrets(self._remoteCommand)))
        _, _, code = yield utils.getProcessOutputAndValue(self._sshBin, args)
        defer.returnValue(code == 0)

    @defer.inlineCallbacks
    def _prepareSshKeys(self, manager, temp_dir_path):
        key_path = None
        if self._sshKey is not None:
            ssh_key_data = yield manager.renderSecrets(self._sshKey)

            key_path = os.path.join(temp_dir_path, 'ssh-key')
            misc.writeLocalFile(key_path, ssh_key_data,
                                mode=stat.S_IRUSR)

        known_hosts_path = None
        if self._sshHostKey is not None:
            ssh_host_key_data = yield manager.renderSecrets(self._sshHostKey)
            ssh_host_key_data = getSshKnownHostsContents(ssh_host_key_data)

            known_hosts_path = os.path.join(temp_dir_path, 'ssh-known-hosts')
            misc.writeLocalFile(known_hosts_path, ssh_host_key_data)

        defer.returnValue((key_path, known_hosts_path))

    @defer.inlineCallbacks
    def execute(self, manager):
        if self._sshKey is not None or self._sshHostKey is not None:
            with private_tempdir.PrivateTemporaryDirectory(
                    prefix='ssh-', dir=manager.master.basedir) as temp_dir:

                key_path, hosts_path = yield self._prepareSshKeys(manager,
                                                                  temp_dir)

                ret = yield self._executeImpl(manager, key_path, hosts_path)
        else:
            ret = yield self._executeImpl(manager, None, None)
        defer.returnValue(ret)


@implementer(interfaces.IMachineWakeAction)
class LocalWakeAction(_LocalMachineActionMixin):
    def __init__(self, command):
        self.setupLocal(command)

    def wake(self, manager):
        return self.execute(manager)


class LocalWOLAction(LocalWakeAction):
    def __init__(self, wakeMac, wolBin='wakeonlan'):
        LocalWakeAction.__init__(self, [wolBin, wakeMac])


@implementer(interfaces.IMachineWakeAction)
class RemoteSshWakeAction(_SshActionMixin):
    def __init__(self, host, remoteCommand, sshBin='ssh',
                 sshKey=None, sshHostKey=None):
        self.setupSsh(sshBin, host, remoteCommand,
                      sshKey=sshKey, sshHostKey=sshHostKey)

    def wake(self, manager):
        return self.execute(manager)


class RemoteSshWOLAction(RemoteSshWakeAction):
    def __init__(self, host, wakeMac, wolBin='wakeonlan', sshBin='ssh',
                 sshKey=None, sshHostKey=None):
        RemoteSshWakeAction.__init__(self, host, [wolBin, wakeMac],
                                     sshBin=sshBin,
                                     sshKey=sshKey, sshHostKey=sshHostKey)


@implementer(interfaces.IMachineSuspendAction)
class RemoteSshSuspendAction(_SshActionMixin):
    def __init__(self, host, remoteCommand=None, sshBin='ssh',
                 sshKey=None, sshHostKey=None):
        if remoteCommand is None:
            remoteCommand = ['systemctl', 'suspend']
        self.setupSsh(sshBin, host, remoteCommand,
                      sshKey=sshKey, sshHostKey=sshHostKey)

    def suspend(self, manager):
        return self.execute(manager)


@implementer(interfaces.ISuspendableMachine)
class SuspendableMachine(service.BuildbotService, object):

    DEFAULT_MISSING_TIMEOUT = 20 * 60

    STATE_SUSPENDED = 0
    STATE_STARTING = 1
    STATE_STARTED = 2
    STATE_SUSPENDING = 3

    def checkConfig(self, name, workernames, wake_action, suspend_action,
                    build_wait_timeout=0,
                    missing_timeout=DEFAULT_MISSING_TIMEOUT, **kwargs):
        self.name = name
        self.workernames = workernames
        self.state = self.STATE_SUSPENDED
        self.workers = []

        if not interfaces.IMachineWakeAction.providedBy(wake_action):
            msg = "wake_action of {} does not implement required " \
                  "interface".format(self.name)
            raise Exception(msg)

        if not interfaces.IMachineSuspendAction.providedBy(suspend_action):
            msg = "suspend_action of {} does not implement required " \
                  "interface".format(self.name)
            raise Exception(msg)

    def reconfigService(self, name, workernames, wake_action, suspend_action,
                        build_wait_timeout=0,
                        missing_timeout=DEFAULT_MISSING_TIMEOUT):
        assert self.name == name
        self.workernames = workernames
        self.wake_action = wake_action
        self.suspend_action = suspend_action
        self.build_wait_timeout = build_wait_timeout
        self.missing_timeout = missing_timeout

        for worker in self.workers:
            worker.machine_manager = None

        self.workers = [self.master.workers.workers[name]
                        for name in self.workernames]

        for worker in self.workers:
            if not interfaces.ISuspendableWorker.providedBy(worker):
                raise Exception('Worker is not suspendable {0}'.format(
                    worker.name))
            worker.machine_manager = self

        self.state = self.STATE_SUSPENDED
        self._start_notifier = Notifier()
        self._suspend_notifier = Notifier()
        self._build_wait_timer = None
        self._missing_timer = None

    @defer.inlineCallbacks
    def start_instance(self, starting_worker):
        if self.state == self.STATE_SUSPENDING:
            # wait until suspend action finishes
            yield self._suspend_notifier.wait()

        if self.state == self.STATE_STARTED:
            # may happen if we waited for suspend to complete and in the mean
            # time the machine was successfully woken.
            defer.returnValue(True)
            return  # pragma: no cover

        # wait for already proceeding startup to finish, if any
        if self.state == self.STATE_STARTING:
            ret = yield self._start_notifier.wait()
            defer.returnValue(ret)
            return  # pragma: no cover

        self.state = self.STATE_STARTING

        # substantiate all workers. We must do so before waking the machine to
        # guarantee that we're already waiting for worker connection as waking
        # may take time confirming machine came online. We'll call substantiate
        # on the worker that invoked this function again, but that's okay as
        # that function is reentrant. Note that we substantiate without
        # gathering results because the original call to substantiate will get
        # them anyway and we don't want to be slowed down by other workers on
        # the machine.
        for worker in self.workers:
            worker.substantiate(None, None)

        # Wake the machine. We don't need to wait for any workers to actually
        # come online as that's handled in their substantiate() functions.
        try:
            ret = yield self.wake_action.wake(self)
        except Exception as e:
            log.err(e, 'while waking suspendable machine {0}'.format(self.name))
            ret = False

        if not ret:
            yield defer.DeferredList([worker.insubstantiate()
                                      for worker in self.workers],
                                     consumeErrors=True)
        else:
            self._setMissingTimer()

        self.state = self.STATE_STARTED if ret else self.STATE_SUSPENDED
        self._start_notifier.notify(ret)

        defer.returnValue(ret)

    @defer.inlineCallbacks
    def _suspend(self):
        if any(worker.building for worker in self.workers) or \
                self.state == self.STATE_STARTING:
            defer.returnValue(None)
            return  # pragma: no cover

        if self.state == self.STATE_SUSPENDING:
            yield self._suspend_notifier.wait()
            defer.returnValue(None)
            return  # pragma: no cover

        self.state = self.STATE_SUSPENDING

        # wait until workers insubstantiate, then suspend
        yield defer.DeferredList([worker.insubstantiate()
                                  for worker in self.workers],
                                 consumeErrors=True)
        try:
            yield self.suspend_action.suspend(self)
        except Exception as e:
            log.err(e, 'while suspending suspendable machine {0}'.format(
                self.name))

        self.state = self.STATE_SUSPENDED
        self._suspend_notifier.notify(None)

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
            self.missing_timeout, self._suspend)

    def _clearBuildWaitTimer(self):
        if self._build_wait_timer is not None:
            if self._build_wait_timer.active():
                self._build_wait_timer.cancel()
            self._build_wait_timer = None

    def _setBuildWaitTimer(self):
        self._clearBuildWaitTimer()
        self._build_wait_timer = self.master.reactor.callLater(
            self.build_wait_timeout, self._suspend)

    def __repr__(self):
        return "<SuspendableMachine '%r' at %d>" % (
            self.name, id(self))
