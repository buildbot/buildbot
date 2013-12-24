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

from buildbot import util
from buildbot.process import metrics
from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.util.eventual import eventually
from twisted.internet import defer
from twisted.internet import error
from twisted.python import log
from twisted.python.failure import Failure
from twisted.spread import pb


class RemoteCommand(pb.Referenceable):

    # class-level unique identifier generator for command ids
    _commandCounter = 0

    active = False
    rc = None
    debug = False

    def __init__(self, remote_command, args, ignore_updates=False,
                 collectStdout=False, collectStderr=False, decodeRC={0: SUCCESS}):
        self.logs = {}
        self.delayedLogs = {}
        self._closeWhenFinished = {}
        self.collectStdout = collectStdout
        self.collectStderr = collectStderr
        self.stdout = ''
        self.stderr = ''
        self.updates = {}

        self._startTime = None
        self._remoteElapsed = None
        self.remote_command = remote_command
        self.args = args
        self.ignore_updates = ignore_updates
        self.decodeRC = decodeRC

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
        # started), and pb.PBConnectionLost (when the slave isn't responding
        # over this connection, perhaps it had a power failure, or NAT
        # weirdness). If this happens, self.deferred is fired right away.
        d.addErrback(self._finished)

        # Connections which are lost while the command is running are caught
        # when our parent Step calls our .lostRemote() method.
        return self.deferred

    def useLog(self, log, closeWhenFinished=False, logfileName=None):
        # note that, for the moment, log is a SyncWriteOnlyLogFileWrapper
        if not logfileName:
            logfileName = log.getName()
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.logs[logfileName] = log
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

    def _finished(self, failure=None):
        self.active = False
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
        if not self.active:
            log.msg(" but this RemoteCommand is already inactive")
            return defer.succeed(None)
        if not self.conn:
            log.msg(" but our .conn went away")
            return defer.succeed(None)
        if isinstance(why, Failure) and why.check(error.ConnectionLost):
            log.msg("RemoteCommand.disconnect: lost slave")
            self.conn = None
            self._finished(why)
            return defer.succeed(None)

        # tell the remote command to halt. Returns a Deferred that will fire
        # when the interrupt command has been delivered.

        d = self.conn.remoteInterruptCommand(self.commandID, str(why))
        # the slave may not have remote_interruptCommand
        d.addErrback(self._interruptFailed)
        return d

    def _interruptFailed(self, why):
        log.msg("RemoteCommand._interruptFailed", self)
        # TODO: forcibly stop the Command now, since we can't stop it
        # cleanly
        return None

    def remote_update(self, updates):
        """
        I am called by the slave's L{buildbot.slave.bot.SlaveBuilder} so
        I can receive updates from the running remote command.

        @type  updates: list of [object, int]
        @param updates: list of updates from the remote command
        """
        self.buildslave.messageReceivedFromSlave()
        max_updatenum = 0
        for (update, num) in updates:
            #log.msg("update[%d]:" % num)
            try:
                if self.active and not self.ignore_updates:
                    self.remoteUpdate(update)
            except:
                # log failure, terminate build, let slave retire the update
                self._finished(Failure())
                # TODO: what if multiple updates arrive? should
                # skip the rest but ack them all
            if num > max_updatenum:
                max_updatenum = num
        return max_updatenum

    def remote_complete(self, failure=None):
        """
        Called by the slave's L{buildbot.slave.bot.SlaveBuilder} to
        notify me the remote command has finished.

        @type  failure: L{twisted.python.failure.Failure} or None

        @rtype: None
        """
        self.buildslave.messageReceivedFromSlave()
        # call the real remoteComplete a moment later, but first return an
        # acknowledgement so the slave can retire the completion message.
        if self.active:
            eventually(self._finished, failure)
        return None

    def addStdout(self, data):
        if 'stdio' in self.logs:
            self.logs['stdio'].addStdout(data)
        if self.collectStdout:
            self.stdout += data

    def addStderr(self, data):
        if 'stdio' in self.logs:
            self.logs['stdio'].addStderr(data)
        if self.collectStderr:
            self.stderr += data

    def addHeader(self, data):
        if 'stdio' in self.logs:
            self.logs['stdio'].addHeader(data)

    def addToLog(self, logname, data):
        # Activate delayed logs on first data.
        if logname in self.delayedLogs:
            (activateCallBack, closeWhenFinished) = self.delayedLogs[logname]
            del self.delayedLogs[logname]
            loog = activateCallBack(self)
            self.logs[logname] = loog
            self._closeWhenFinished[logname] = closeWhenFinished

        if logname in self.logs:
            self.logs[logname].addStdout(data)
        else:
            log.msg("%s.addToLog: no such log %s" % (self, logname))

    @metrics.countMethod('RemoteCommand.remoteUpdate()')
    def remoteUpdate(self, update):
        if self.debug:
            for k, v in update.items():
                log.msg("Update[%s]: %s" % (k, v))
        if "stdout" in update:
            # 'stdout': data
            self.addStdout(update['stdout'])
        if "stderr" in update:
            # 'stderr': data
            self.addStderr(update['stderr'])
        if "header" in update:
            # 'header': data
            self.addHeader(update['header'])
        if "log" in update:
            # 'log': (logname, data)
            logname, data = update['log']
            self.addToLog(logname, data)
        if "rc" in update:
            rc = self.rc = update['rc']
            log.msg("%s rc=%s" % (self, rc))
            self.addHeader("program finished with exit code %d\n" % rc)
        if "elapsed" in update:
            self._remoteElapsed = update['elapsed']

        # TODO: these should be handled at the RemoteCommand level
        for k in update:
            if k not in ('stdout', 'stderr', 'header', 'rc'):
                if k not in self.updates:
                    self.updates[k] = []
                self.updates[k].append(update[k])

    def remoteComplete(self, maybeFailure):
        if self._startTime and self._remoteElapsed:
            delta = (util.now() - self._startTime) - self._remoteElapsed
            metrics.MetricTimeEvent.log("RemoteCommand.overhead", delta)

        for name, loog in self.logs.items():
            if self._closeWhenFinished[name]:
                if maybeFailure:
                    loog.addHeader("\nremoteFailed: %s" % maybeFailure)
                else:
                    log.msg("closing log %s" % loog)
                loog.finish()
        return maybeFailure

    def results(self):
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
                 logfiles={}, usePTY="slave-config", logEnviron=True,
                 collectStdout=False, collectStderr=False,
                 interruptSignal=None,
                 initialStdin=None, decodeRC={0: SUCCESS}):

        self.command = command  # stash .command, set it later
        if isinstance(self.command, basestring):
            # Single string command doesn't support obfuscation.
            self.fake_command = command
        else:
            # Try to obfuscate command.
            def obfuscate(arg):
                if isinstance(arg, tuple) and len(arg) == 3 and arg[0] == 'obfuscated':
                    return arg[2]
                else:
                    return arg
            self.fake_command = map(obfuscate, self.command)

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
        RemoteCommand.__init__(self, "shell", args, collectStdout=collectStdout,
                               collectStderr=collectStderr,
                               decodeRC=decodeRC)

    def _start(self):
        self.args['command'] = self.command
        if self.remote_command == "shell":
            # non-ShellCommand slavecommands are responsible for doing this
            # fixup themselves
            if self.step.slaveVersion("shell", "old") == "old":
                self.args['dir'] = self.args['workdir']
            if not self.step.slaveVersionIsOlderThan("shell", "2.16"):
                self.args.pop('sigtermTime', None)
        what = "command '%s' in dir '%s'" % (self.fake_command,
                                             self.args['workdir'])
        log.msg(what)
        return RemoteCommand._start(self)

    def __repr__(self):
        return "<RemoteShellCommand '%s'>" % repr(self.fake_command)
