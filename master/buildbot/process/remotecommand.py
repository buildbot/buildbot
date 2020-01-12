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

from twisted.internet import defer
from twisted.internet import error
from twisted.python import log
from twisted.python.failure import Failure
from twisted.spread import pb

from buildbot import util
from buildbot.pbutil import decode
from buildbot.process import metrics
from buildbot.process.results import CANCELLED
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.util.eventual import eventually
from buildbot.worker.protocols import base


class RemoteException(Exception):
    pass


class RemoteCommand(base.RemoteCommandImpl):

    # class-level unique identifier generator for command ids
    _commandCounter = 0

    active = False
    rc = None
    debug = False

    def __init__(self, remote_command, args, ignore_updates=False,
                 collectStdout=False, collectStderr=False, decodeRC=None,
                 stdioLogName='stdio'):
        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        self.logs = {}
        self.delayedLogs = {}
        self._closeWhenFinished = {}
        self.collectStdout = collectStdout
        self.collectStderr = collectStderr
        self.stdout = ''
        self.stderr = ''
        self.updates = {}
        self.stdioLogName = stdioLogName
        self._startTime = None
        self._remoteElapsed = None
        self.remote_command = remote_command
        self.args = args
        self.ignore_updates = ignore_updates
        self.decodeRC = decodeRC
        self.conn = None
        self.worker = None
        self.step = None
        self.builder_name = None
        self.commandID = None
        self.deferred = None
        self.interrupted = False
        # a lock to make sure that only one log-handling method runs at a time.
        # This is really only a problem with old-style steps, which do not
        # wait for the Deferred from one method before invoking the next.
        self.loglock = defer.DeferredLock()

    def __repr__(self):
        return "<RemoteCommand '%s' at %d>" % (self.remote_command, id(self))

    def run(self, step, conn, builder_name):
        self.active = True
        self.step = step
        self.conn = conn
        self.builder_name = builder_name

        # generate a new command id
        cmd_id = RemoteCommand._commandCounter
        RemoteCommand._commandCounter += 1
        self.commandID = "%d" % cmd_id

        log.msg("%s: RemoteCommand.run [%s]" % (self, self.commandID))
        self.deferred = defer.Deferred()

        d = defer.maybeDeferred(self._start)

        # _finished is called with an error for unknown commands, errors
        # that occur while the command is starting (including OSErrors in
        # exec()), StaleBroker (when the connection was lost before we
        # started), and pb.PBConnectionLost (when the worker isn't responding
        # over this connection, perhaps it had a power failure, or NAT
        # weirdness). If this happens, self.deferred is fired right away.
        d.addErrback(self._finished)

        # Connections which are lost while the command is running are caught
        # when our parent Step calls our .lostRemote() method.
        return self.deferred

    def useLog(self, log_, closeWhenFinished=False, logfileName=None):
        # NOTE: log may be a SyngLogFileWrapper or a Log instance, depending on
        # the step
        if not logfileName:
            logfileName = log_.getName()
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.logs[logfileName] = log_
        self._closeWhenFinished[logfileName] = closeWhenFinished

    def useLogDelayed(self, logfileName, activateCallBack, closeWhenFinished=False):
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.delayedLogs[logfileName] = (activateCallBack, closeWhenFinished)

    def _start(self):
        self._startTime = util.now()
        # This method only initiates the remote command.
        # We will receive remote_update messages as the command runs.
        # We will get a single remote_complete when it finishes.
        # We should fire self.deferred when the command is done.
        d = self.conn.remoteStartCommand(self, self.builder_name,
                                         self.commandID, self.remote_command,
                                         self.args)
        return d

    @defer.inlineCallbacks
    def _finished(self, failure=None):
        self.active = False
        # the rc is send asynchronously and there is a chance it is still in the callback queue
        # when finished is received, we have to workaround in the master because worker might be older
        timeout = 10
        while self.rc is None and timeout > 0:
            yield util.asyncSleep(.1)
            timeout -= 1
        # call .remoteComplete. If it raises an exception, or returns the
        # Failure that we gave it, our self.deferred will be errbacked. If
        # it does not (either it ate the Failure or there the step finished
        # normally and it didn't raise a new exception), self.deferred will
        # be callbacked.
        d = defer.maybeDeferred(self.remoteComplete, failure)
        # arrange for the callback to get this RemoteCommand instance
        # instead of just None
        d.addCallback(lambda r: self)
        # this fires the original deferred we returned from .run(),
        # with self as the result, or a failure
        d.addBoth(self.deferred.callback)

    def interrupt(self, why):
        log.msg("RemoteCommand.interrupt", self, why)
        if not self.active or self.interrupted:
            log.msg(" but this RemoteCommand is already inactive")
            return defer.succeed(None)
        if not self.conn:
            log.msg(" but our .conn went away")
            return defer.succeed(None)
        if isinstance(why, Failure) and why.check(error.ConnectionLost):
            log.msg("RemoteCommand.disconnect: lost worker")
            self.conn = None
            self._finished(why)
            return defer.succeed(None)

        self.interrupted = True
        # tell the remote command to halt. Returns a Deferred that will fire
        # when the interrupt command has been delivered.
        d = self.conn.remoteInterruptCommand(self.builder_name,
                                             self.commandID, str(why))
        # the worker may not have remote_interruptCommand
        d.addErrback(self._interruptFailed)
        return d

    def _interruptFailed(self, why):
        log.msg("RemoteCommand._interruptFailed", self)
        # TODO: forcibly stop the Command now, since we can't stop it
        # cleanly
        return None

    def remote_update(self, updates):
        """
        I am called by the worker's
        L{buildbot_worker.base.WorkerForBuilderBase.sendUpdate} so
        I can receive updates from the running remote command.

        @type  updates: list of [object, int]
        @param updates: list of updates from the remote command
        """
        updates = decode(updates)
        self.worker.messageReceivedFromWorker()
        max_updatenum = 0
        for (update, num) in updates:
            # log.msg("update[%d]:" % num)
            try:
                if self.active and not self.ignore_updates:
                    self.remoteUpdate(update)
            except Exception:
                # log failure, terminate build, let worker retire the update
                self._finished(Failure())
                # TODO: what if multiple updates arrive? should
                # skip the rest but ack them all
            if num > max_updatenum:
                max_updatenum = num
        return max_updatenum

    def remote_complete(self, failure=None):
        """
        Called by the worker's
        L{buildbot_worker.base.WorkerForBuilderBase.commandComplete} to
        notify me the remote command has finished.

        @type  failure: L{twisted.python.failure.Failure} or None

        @rtype: None
        """
        self.worker.messageReceivedFromWorker()
        # call the real remoteComplete a moment later, but first return an
        # acknowledgement so the worker can retire the completion message.
        if self.active:
            eventually(self._finished, failure)
        return None

    def _unwrap(self, log):
        from buildbot.process import buildstep
        if isinstance(log, buildstep.SyncLogFileWrapper):
            return log.unwrap()
        return log

    @util.deferredLocked('loglock')
    @defer.inlineCallbacks
    def addStdout(self, data):
        if self.collectStdout:
            self.stdout += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            log_ = yield self._unwrap(self.logs[self.stdioLogName])
            log_.addStdout(data)

    @util.deferredLocked('loglock')
    @defer.inlineCallbacks
    def addStderr(self, data):
        if self.collectStderr:
            self.stderr += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            log_ = yield self._unwrap(self.logs[self.stdioLogName])
            log_.addStderr(data)

    @util.deferredLocked('loglock')
    @defer.inlineCallbacks
    def addHeader(self, data):
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            log_ = yield self._unwrap(self.logs[self.stdioLogName])
            log_.addHeader(data)

    @util.deferredLocked('loglock')
    @defer.inlineCallbacks
    def addToLog(self, logname, data):
        # Activate delayed logs on first data.
        if logname in self.delayedLogs:
            (activateCallBack, closeWhenFinished) = self.delayedLogs[logname]
            del self.delayedLogs[logname]
            loog = yield activateCallBack(self)
            loog = yield self._unwrap(loog)
            self.logs[logname] = loog
            self._closeWhenFinished[logname] = closeWhenFinished

        if logname in self.logs:
            log_ = yield self._unwrap(self.logs[logname])
            yield log_.addStdout(data)
        else:
            log.msg("%s.addToLog: no such log %s" % (self, logname))

    @metrics.countMethod('RemoteCommand.remoteUpdate()')
    @defer.inlineCallbacks
    def remoteUpdate(self, update):
        def cleanup(data):
            if self.step is None:
                return data
            return self.step.build.properties.cleanupTextFromSecrets(data)

        if self.debug:
            for k, v in update.items():
                log.msg("Update[%s]: %s" % (k, v))
        if "stdout" in update:
            # 'stdout': data
            yield self.addStdout(cleanup(update['stdout']))
        if "stderr" in update:
            # 'stderr': data
            yield self.addStderr(cleanup(update['stderr']))
        if "header" in update:
            # 'header': data
            yield self.addHeader(cleanup(update['header']))
        if "log" in update:
            # 'log': (logname, data)
            logname, data = update['log']
            yield self.addToLog(logname, cleanup(data))
        if "rc" in update:
            rc = self.rc = update['rc']
            log.msg("%s rc=%s" % (self, rc))
            yield self.addHeader("program finished with exit code %d\n" % rc)
        if "elapsed" in update:
            self._remoteElapsed = update['elapsed']

        # TODO: these should be handled at the RemoteCommand level
        for k in update:
            if k not in ('stdout', 'stderr', 'header', 'rc'):
                if k not in self.updates:
                    self.updates[k] = []
                self.updates[k].append(update[k])

    @util.deferredLocked('loglock')
    @defer.inlineCallbacks
    def remoteComplete(self, maybeFailure):
        if self._startTime and self._remoteElapsed:
            delta = (util.now() - self._startTime) - self._remoteElapsed
            metrics.MetricTimeEvent.log("RemoteCommand.overhead", delta)

        for name, loog in self.logs.items():
            if self._closeWhenFinished[name]:
                if maybeFailure:
                    loog = yield self._unwrap(loog)
                    yield loog.addHeader("\nremoteFailed: %s" % maybeFailure)
                else:
                    log.msg("closing log %s" % loog)
                loog.finish()
        if maybeFailure:
            # workaround http://twistedmatrix.com/trac/ticket/5507
            # CopiedFailure cannot be raised back, this make debug difficult
            if isinstance(maybeFailure, pb.CopiedFailure):
                maybeFailure.value = RemoteException("%s: %s\n%s" % (
                    maybeFailure.type, maybeFailure.value, maybeFailure.traceback))
                maybeFailure.type = RemoteException
            maybeFailure.raiseException()

    def results(self):
        if self.interrupted:
            return CANCELLED
        if self.rc in self.decodeRC:
            return self.decodeRC[self.rc]
        return FAILURE

    def didFail(self):
        return self.results() == FAILURE


LoggedRemoteCommand = RemoteCommand


class RemoteShellCommand(RemoteCommand):

    def __init__(self, workdir, command, env=None,
                 want_stdout=1, want_stderr=1,
                 timeout=20 * 60, maxTime=None, sigtermTime=None,
                 logfiles=None, usePTY=None, logEnviron=True,
                 collectStdout=False, collectStderr=False,
                 interruptSignal=None,
                 initialStdin=None, decodeRC=None,
                 stdioLogName='stdio'):
        if logfiles is None:
            logfiles = {}
        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        self.command = command  # stash .command, set it later
        if isinstance(self.command, (str, bytes)):
            # Single string command doesn't support obfuscation.
            self.fake_command = command
        else:
            # Try to obfuscate command.
            def obfuscate(arg):
                if isinstance(arg, tuple) and len(arg) == 3 and arg[0] == 'obfuscated':
                    return arg[2]
                return arg
            self.fake_command = [obfuscate(c) for c in self.command]

        if env is not None:
            # avoid mutating the original master.cfg dictionary. Each
            # ShellCommand gets its own copy, any start() methods won't be
            # able to modify the original.
            env = env.copy()

        args = {'workdir': workdir,
                'env': env,
                'want_stdout': want_stdout,
                'want_stderr': want_stderr,
                'logfiles': logfiles,
                'timeout': timeout,
                'maxTime': maxTime,
                'sigtermTime': sigtermTime,
                'usePTY': usePTY,
                'logEnviron': logEnviron,
                'initial_stdin': initialStdin
                }
        if interruptSignal is not None:
            args['interruptSignal'] = interruptSignal
        super().__init__("shell", args, collectStdout=collectStdout,
                         collectStderr=collectStderr,
                         decodeRC=decodeRC,
                         stdioLogName=stdioLogName)

    def _start(self):
        if self.args['usePTY'] is None:
            if self.step.workerVersionIsOlderThan("shell", "3.0"):
                # Old worker default of usePTY is to use worker-configuration.
                self.args['usePTY'] = "slave-config"
            else:
                # buildbot-worker doesn't support worker-configured usePTY,
                # and usePTY defaults to False.
                self.args['usePTY'] = False

        self.args['command'] = self.command
        if self.remote_command == "shell":
            # non-ShellCommand worker commands are responsible for doing this
            # fixup themselves
            if self.step.workerVersion("shell", "old") == "old":
                self.args['dir'] = self.args['workdir']
            if self.step.workerVersionIsOlderThan("shell", "2.16"):
                self.args.pop('sigtermTime', None)
        what = "command '%s' in dir '%s'" % (self.fake_command,
                                             self.args['workdir'])
        log.msg(what)
        return super()._start()

    def __repr__(self):
        return "<RemoteShellCommand '%s'>" % repr(self.fake_command)
