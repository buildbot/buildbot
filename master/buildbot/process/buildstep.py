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


import re

from zope.interface import implements
from twisted.internet import reactor, defer, error
from twisted.protocols import basic
from twisted.spread import pb
from twisted.python import log
from twisted.python.failure import Failure
from twisted.web.util import formatFailure
from twisted.python.reflect import accumulateClassList

from buildbot import interfaces, locks, util
from buildbot.status import progress
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE, SKIPPED, \
     EXCEPTION, RETRY, worst_status
from buildbot.process import metrics

"""
BuildStep and RemoteCommand classes for master-side representation of the
build process
"""

class RemoteCommand(pb.Referenceable):
    """
    I represent a single command to be run on the slave. I handle the details
    of reliably gathering status updates from the slave (acknowledging each),
    and (eventually, in a future release) recovering from interrupted builds.
    This is the master-side object that is known to the slave-side
    L{buildbot.slave.bot.SlaveBuilder}, to which status updates are sent.

    My command should be started by calling .run(), which returns a
    Deferred that will fire when the command has finished, or will
    errback if an exception is raised.
    
    Typically __init__ or run() will set up self.remote_command to be a
    string which corresponds to one of the SlaveCommands registered in
    the buildslave, and self.args to a dictionary of arguments that will
    be passed to the SlaveCommand instance.

    start, remoteUpdate, and remoteComplete are available to be overridden

    @type  commandCounter: list of one int
    @cvar  commandCounter: provides a unique value for each
                           RemoteCommand executed across all slaves
    @type  active:         boolean
    @ivar  active:         whether the command is currently running
    """
    commandCounter = [0] # we use a list as a poor man's singleton
    active = False

    def __init__(self, remote_command, args):
        """
        @type  remote_command: string
        @param remote_command: remote command to start.  This will be
                               passed to
                               L{buildbot.slave.bot.SlaveBuilder.remote_startCommand}
                               and needs to have been registered
                               slave-side in L{buildbot.slave.registry}
        @type  args:           dict
        @param args:           arguments to send to the remote command
        """

        self.remote_command = remote_command
        self.args = args

    def run(self, step, remote):
        self.active = True
        self.step = step
        self.remote = remote
        c = self.commandCounter[0]
        self.commandCounter[0] += 1
        #self.commandID = "%d %d" % (c, random.randint(0, 1000000))
        self.commandID = "%d" % c
        log.msg("%s: RemoteCommand.run [%s]" % (self, self.commandID))
        self.deferred = defer.Deferred()

        d = defer.maybeDeferred(self.start)

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

    def start(self):
        """
        Tell the slave to start executing the remote command.

        @rtype:   L{twisted.internet.defer.Deferred}
        @returns: a deferred that will fire when the remote command is
                  done (with None as the result)
        """

        # Allow use of WithProperties in logfile path names.
        cmd_args = self.args
        if cmd_args.has_key("logfiles") and cmd_args["logfiles"]:
            cmd_args = cmd_args.copy()
            cmd_args["logfiles"] = self.step.build.render(cmd_args["logfiles"])

        # This method only initiates the remote command.
        # We will receive remote_update messages as the command runs.
        # We will get a single remote_complete when it finishes.
        # We should fire self.deferred when the command is done.
        d = self.remote.callRemote("startCommand", self, self.commandID,
                                   self.remote_command, cmd_args)
        return d

    def interrupt(self, why):
        # TODO: consider separating this into interrupt() and stop(), where
        # stop() unconditionally calls _finished, but interrupt() merely
        # asks politely for the command to stop soon.

        log.msg("RemoteCommand.interrupt", self, why)
        if not self.active:
            log.msg(" but this RemoteCommand is already inactive")
            return
        if not self.remote:
            log.msg(" but our .remote went away")
            return
        if isinstance(why, Failure) and why.check(error.ConnectionLost):
            log.msg("RemoteCommand.disconnect: lost slave")
            self.remote = None
            self._finished(why)
            return

        # tell the remote command to halt. Returns a Deferred that will fire
        # when the interrupt command has been delivered.
        
        d = defer.maybeDeferred(self.remote.callRemote, "interruptCommand",
                                self.commandID, str(why))
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
                if self.active: # ignore late updates
                    self.remoteUpdate(update)
            except:
                # log failure, terminate build, let slave retire the update
                self._finished(Failure())
                # TODO: what if multiple updates arrive? should
                # skip the rest but ack them all
            if num > max_updatenum:
                max_updatenum = num
        return max_updatenum

    def remoteUpdate(self, update):
        raise NotImplementedError("You must implement this in a subclass")

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
            reactor.callLater(0, self._finished, failure)
        return None

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

    def remoteComplete(self, maybeFailure):
        """Subclasses can override this.

        This is called when the RemoteCommand has finished. 'maybeFailure'
        will be None if the command completed normally, or a Failure
        instance in one of the following situations:

         - the slave was lost before the command was started
         - the slave didn't respond to the startCommand message
         - the slave raised an exception while starting the command
           (bad command name, bad args, OSError from missing executable)
         - the slave raised an exception while finishing the command
           (they send back a remote_complete message with a Failure payload)

        and also (for now):
         -  slave disconnected while the command was running
        
        This method should do cleanup, like closing log files. It should
        normally return the 'failure' argument, so that any exceptions will
        be propagated to the Step. If it wants to consume them, return None
        instead."""

        return maybeFailure

class LoggedRemoteCommand(RemoteCommand):
    """

    I am a L{RemoteCommand} which gathers output from the remote command into
    one or more local log files. My C{self.logs} dictionary contains
    references to these L{buildbot.status.logfile.LogFile} instances. Any
    stdout/stderr/header updates from the slave will be put into
    C{self.logs['stdio']}, if it exists. If the remote command uses other log
    files, they will go into other entries in C{self.logs}.

    If you want to use stdout or stderr, you should create a LogFile named
    'stdio' and pass it to my useLog() message. Otherwise stdout/stderr will
    be ignored, which is probably not what you want.

    Unless you tell me otherwise, when my command completes I will close all
    the LogFiles that I know about.

    @ivar logs: maps logname to a LogFile instance
    @ivar _closeWhenFinished: maps logname to a boolean. If true, this
                              LogFile will be closed when the RemoteCommand
                              finishes. LogFiles which are shared between
                              multiple RemoteCommands should use False here.

    """

    rc = None
    debug = False

    def __init__(self, *args, **kwargs):
        self.logs = {}
        self.delayedLogs = {}
        self._closeWhenFinished = {}
        RemoteCommand.__init__(self, *args, **kwargs)

    def __repr__(self):
        return "<RemoteCommand '%s' at %d>" % (self.remote_command, id(self))

    def useLog(self, loog, closeWhenFinished=False, logfileName=None):
        """Start routing messages from a remote logfile to a local LogFile

        I take a local ILogFile instance in 'loog', and arrange to route
        remote log messages for the logfile named 'logfileName' into it. By
        default this logfileName comes from the ILogFile itself (using the
        name by which the ILogFile will be displayed), but the 'logfileName'
        argument can be used to override this. For example, if
        logfileName='stdio', this logfile will collect text from the stdout
        and stderr of the command.

        @param loog: an instance which implements ILogFile
        @param closeWhenFinished: a boolean, set to False if the logfile
                                  will be shared between multiple
                                  RemoteCommands. If True, the logfile will
                                  be closed when this ShellCommand is done
                                  with it.
        @param logfileName: a string, which indicates which remote log file
                            should be routed into this ILogFile. This should
                            match one of the keys of the logfiles= argument
                            to ShellCommand.

        """

        assert interfaces.ILogFile.providedBy(loog)
        if not logfileName:
            logfileName = loog.getName()
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.logs[logfileName] = loog
        self._closeWhenFinished[logfileName] = closeWhenFinished
        self._startTime = None
        self._remoteElapsed = None

    def useLogDelayed(self, logfileName, activateCallBack, closeWhenFinished=False):
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.delayedLogs[logfileName] = (activateCallBack, closeWhenFinished)

    def start(self):
        log.msg("LoggedRemoteCommand.start")
        if 'stdio' not in self.logs:
            log.msg("LoggedRemoteCommand (%s) is running a command, but "
                    "it isn't being logged to anything. This seems unusual."
                    % self)
        self.updates = {}
        self._startTime = util.now()
        return RemoteCommand.start(self)

    def addStdout(self, data):
        if 'stdio' in self.logs:
            self.logs['stdio'].addStdout(data)
    def addStderr(self, data):
        if 'stdio' in self.logs:
            self.logs['stdio'].addStderr(data)
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

    @metrics.countMethod('LoggedRemoteCommand.remoteUpdate()')
    def remoteUpdate(self, update):
        if self.debug:
            for k,v in update.items():
                log.msg("Update[%s]: %s" % (k,v))
        if update.has_key('stdout'):
            # 'stdout': data
            self.addStdout(update['stdout'])
        if update.has_key('stderr'):
            # 'stderr': data
            self.addStderr(update['stderr'])
        if update.has_key('header'):
            # 'header': data
            self.addHeader(update['header'])
        if update.has_key('log'):
            # 'log': (logname, data)
            logname, data = update['log']
            self.addToLog(logname, data)
        if update.has_key('rc'):
            rc = self.rc = update['rc']
            log.msg("%s rc=%s" % (self, rc))
            self.addHeader("program finished with exit code %d\n" % rc)
        if update.has_key('elapsed'):
            self._remoteElapsed = update['elapsed']

        for k in update:
            if k not in ('stdout', 'stderr', 'header', 'rc'):
                if k not in self.updates:
                    self.updates[k] = []
                self.updates[k].append(update[k])

    def remoteComplete(self, maybeFailure):
        if self._startTime and self._remoteElapsed:
            delta = (util.now() - self._startTime) - self._remoteElapsed
            metrics.MetricTimeEvent.log("LoggedRemoteCommand.overhead", delta)

        for name,loog in self.logs.items():
            if self._closeWhenFinished[name]:
                if maybeFailure:
                    loog.addHeader("\nremoteFailed: %s" % maybeFailure)
                else:
                    log.msg("closing log %s" % loog)
                loog.finish()
        return maybeFailure


class LogObserver:
    implements(interfaces.ILogObserver)

    def setStep(self, step):
        self.step = step

    def setLog(self, loog):
        assert interfaces.IStatusLog.providedBy(loog)
        loog.subscribe(self, True)

    def logChunk(self, build, step, log, channel, text):
        if channel == interfaces.LOG_CHANNEL_STDOUT:
            self.outReceived(text)
        elif channel == interfaces.LOG_CHANNEL_STDERR:
            self.errReceived(text)

    # TODO: add a logEnded method? er, stepFinished?

    def outReceived(self, data):
        """This will be called with chunks of stdout data. Override this in
        your observer."""
        pass

    def errReceived(self, data):
        """This will be called with chunks of stderr data. Override this in
        your observer."""
        pass


class LogLineObserver(LogObserver):
    def __init__(self):
        self.stdoutParser = basic.LineOnlyReceiver()
        self.stdoutParser.delimiter = "\n"
        self.stdoutParser.lineReceived = self.outLineReceived
        self.stdoutParser.transport = self # for the .disconnecting attribute
        self.disconnecting = False

        self.stderrParser = basic.LineOnlyReceiver()
        self.stderrParser.delimiter = "\n"
        self.stderrParser.lineReceived = self.errLineReceived
        self.stderrParser.transport = self

    def setMaxLineLength(self, max_length):
        """
        Set the maximum line length: lines longer than max_length are
        dropped.  Default is 16384 bytes.  Use sys.maxint for effective
        infinity.
        """
        self.stdoutParser.MAX_LENGTH = max_length
        self.stderrParser.MAX_LENGTH = max_length

    def outReceived(self, data):
        self.stdoutParser.dataReceived(data)

    def errReceived(self, data):
        self.stderrParser.dataReceived(data)

    def outLineReceived(self, line):
        """This will be called with complete stdout lines (not including the
        delimiter). Override this in your observer."""
        pass

    def errLineReceived(self, line):
        """This will be called with complete lines of stderr (not including
        the delimiter). Override this in your observer."""
        pass


class RemoteShellCommand(LoggedRemoteCommand):
    """This class helps you run a shell command on the build slave. It will
    accumulate all the command's output into a Log named 'stdio'. When the
    command is finished, it will fire a Deferred. You can then check the
    results of the command and parse the output however you like."""

    def __init__(self, workdir, command, env=None,
                 want_stdout=1, want_stderr=1,
                 timeout=20*60, maxTime=None, logfiles={},
                 usePTY="slave-config", logEnviron=True):
        """
        @type  workdir: string
        @param workdir: directory where the command ought to run,
                        relative to the Builder's home directory. Defaults to
                        '.': the same as the Builder's homedir. This should
                        probably be '.' for the initial 'cvs checkout'
                        command (which creates a workdir), and the Build-wide
                        workdir for all subsequent commands (including
                        compiles and 'cvs update').

        @type  command: list of strings (or string)
        @param command: the shell command to run, like 'make all' or
                        'cvs update'. This should be a list or tuple
                        which can be used directly as the argv array.
                        For backwards compatibility, if this is a
                        string, the text will be given to '/bin/sh -c
                        %s'.

        @type  env:     dict of string->string
        @param env:     environment variables to add or change for the
                        slave.  Each command gets a separate
                        environment; all inherit the slave's initial
                        one.  TODO: make it possible to delete some or
                        all of the slave's environment.

        @type  want_stdout: bool
        @param want_stdout: defaults to True. Set to False if stdout should
                            be thrown away. Do this to avoid storing or
                            sending large amounts of useless data.

        @type  want_stderr: bool
        @param want_stderr: False if stderr should be thrown away

        @type  timeout: int
        @param timeout: tell the remote that if the command fails to
                        produce any output for this number of seconds,
                        the command is hung and should be killed. Use
                        None to disable the timeout.

        @param logEnviron: whether to log env vars on the slave side

        @type  maxTime: int
        @param maxTime: tell the remote that if the command fails to complete
                        in this number of seconds, the command should be
                        killed.  Use None to disable maxTime.
        """

        self.command = command # stash .command, set it later
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
                'usePTY': usePTY,
                'logEnviron': logEnviron,
                }
        LoggedRemoteCommand.__init__(self, "shell", args)

    def start(self):
        self.args['command'] = self.command
        if self.remote_command == "shell":
            # non-ShellCommand slavecommands are responsible for doing this
            # fixup themselves
            if self.step.slaveVersion("shell", "old") == "old":
                self.args['dir'] = self.args['workdir']
        what = "command '%s' in dir '%s'" % (self.args['command'],
                                             self.args['workdir'])
        log.msg(what)
        return LoggedRemoteCommand.start(self)

    def __repr__(self):
        return "<RemoteShellCommand '%s'>" % repr(self.command)

class BuildStep:
    """
    I represent a single step of the build process. This step may involve
    zero or more commands to be run in the build slave, as well as arbitrary
    processing on the master side. Regardless of how many slave commands are
    run, the BuildStep will result in a single status value.

    The step is started by calling startStep(), which returns a Deferred that
    fires when the step finishes. See C{startStep} for a description of the
    results provided by that Deferred.

    __init__ and start are good methods to override. Don't forget to upcall
    BuildStep.__init__ or bad things will happen.

    To launch a RemoteCommand, pass it to .runCommand and wait on the
    Deferred it returns.

    Each BuildStep generates status as it runs. This status data is fed to
    the L{buildbot.status.buildstep.BuildStepStatus} listener that sits in
    C{self.step_status}. It can also feed progress data (like how much text
    is output by a shell command) to the
    L{buildbot.status.progress.StepProgress} object that lives in
    C{self.progress}, by calling C{self.setProgress(metric, value)} as it
    runs.

    @type build: L{buildbot.process.build.Build}
    @ivar build: the parent Build which is executing this step

    @type progress: L{buildbot.status.progress.StepProgress}
    @ivar progress: tracks ETA for the step

    @type step_status: L{buildbot.status.buildstep.BuildStepStatus}
    @ivar step_status: collects output status
    """

    # these parameters are used by the parent Build object to decide how to
    # interpret our results. haltOnFailure will affect the build process
    # immediately, the others will be taken into consideration when
    # determining the overall build status.
    #
    # steps that are marked as alwaysRun will be run regardless of the outcome
    # of previous steps (especially steps with haltOnFailure=True)
    haltOnFailure = False
    flunkOnWarnings = False
    flunkOnFailure = False
    warnOnWarnings = False
    warnOnFailure = False
    alwaysRun = False

    # 'parms' holds a list of all the parameters we care about, to allow
    # users to instantiate a subclass of BuildStep with a mixture of
    # arguments, some of which are for us, some of which are for the subclass
    # (or a delegate of the subclass, like how ShellCommand delivers many
    # arguments to the RemoteShellCommand that it creates). Such delegating
    # subclasses will use this list to figure out which arguments are meant
    # for us and which should be given to someone else.
    parms = ['name', 'locks',
             'haltOnFailure',
             'flunkOnWarnings',
             'flunkOnFailure',
             'warnOnWarnings',
             'warnOnFailure',
             'alwaysRun',
             'progressMetrics',
             'doStepIf',
             ]

    name = "generic"
    locks = []
    progressMetrics = () # 'time' is implicit
    useProgress = True # set to False if step is really unpredictable
    build = None
    step_status = None
    progress = None
    # doStepIf can be False, True, or a function that returns False or True
    doStepIf = True

    def __init__(self, **kwargs):
        self.factory = (self.__class__, dict(kwargs))
        for p in self.__class__.parms:
            if kwargs.has_key(p):
                setattr(self, p, kwargs[p])
                del kwargs[p]
        if kwargs:
            why = "%s.__init__ got unexpected keyword argument(s) %s" \
                  % (self, kwargs.keys())
            raise TypeError(why)
        self._pendingLogObservers = []

        self._acquiringLock = None
        self.stopped = False

    def describe(self, done=False):
        return [self.name]

    def setBuild(self, build):
        # subclasses which wish to base their behavior upon qualities of the
        # Build (e.g. use the list of changed files to run unit tests only on
        # code which has been modified) should do so here. The Build is not
        # available during __init__, but setBuild() will be called just
        # afterwards.
        self.build = build

    def setBuildSlave(self, buildslave):
        self.buildslave = buildslave

    def setDefaultWorkdir(self, workdir):
        # The Build calls this just after __init__().  ShellCommand
        # and variants use a slave-side workdir, but some other steps
        # do not. Subclasses which use a workdir should use the value
        # set by this method unless they were constructed with
        # something more specific.
        pass

    def addFactoryArguments(self, **kwargs):
        self.factory[1].update(kwargs)

    def getStepFactory(self):
        return self.factory

    def setStepStatus(self, step_status):
        self.step_status = step_status

    def setupProgress(self):
        if self.useProgress:
            sp = progress.StepProgress(self.name, self.progressMetrics)
            self.progress = sp
            self.step_status.setProgress(sp)
            return sp
        return None

    def setProgress(self, metric, value):
        """BuildSteps can call self.setProgress() to announce progress along
        some metric."""
        if self.progress:
            self.progress.setProgress(metric, value)

    def getProperty(self, propname):
        return self.build.getProperty(propname)

    def setProperty(self, propname, value, source="Step", runtime=True):
        self.build.setProperty(propname, value, source, runtime=runtime)

    def startStep(self, remote):
        """Begin the step. This returns a Deferred that will fire when the
        step finishes.

        This deferred fires with a tuple of (result, [extra text]), although
        older steps used to return just the 'result' value, so the receiving
        L{base.Build} needs to be prepared to handle that too. C{result} is
        one of the SUCCESS/WARNINGS/FAILURE/SKIPPED constants from
        L{buildbot.status.builder}, and the extra text is a list of short
        strings which should be appended to the Build's text results. This
        text allows a test-case step which fails to append B{17 tests} to the
        Build's status, in addition to marking the build as failing.

        The deferred will errback if the step encounters an exception,
        including an exception on the slave side (or if the slave goes away
        altogether). Failures in shell commands (rc!=0) will B{not} cause an
        errback, in general the BuildStep will evaluate the results and
        decide whether to treat it as a WARNING or FAILURE.

        @type remote: L{twisted.spread.pb.RemoteReference}
        @param remote: a reference to the slave's
                       L{buildbot.slave.bot.SlaveBuilder} instance where any
                       RemoteCommands may be run
        """

        self.remote = remote
        self.deferred = defer.Deferred()
        # convert all locks into their real form
        lock_list = []
        for access in self.locks:
            if not isinstance(access, locks.LockAccess):
                # Buildbot 0.7.7 compability: user did not specify access
                access = access.defaultAccess()
            lock = self.build.builder.botmaster.getLockByID(access.lockid)
            lock_list.append((lock, access))
        self.locks = lock_list
        # then narrow SlaveLocks down to the slave that this build is being
        # run on
        self.locks = [(l.getLock(self.build.slavebuilder), la) for l, la in self.locks]
        for l, la in self.locks:
            if l in self.build.locks:
                log.msg("Hey, lock %s is claimed by both a Step (%s) and the"
                        " parent Build (%s)" % (l, self, self.build))
                raise RuntimeError("lock claimed by both Step and Build")

        # Set the step's text here so that the stepStarted notification sees
        # the correct description
        self.step_status.setText(self.describe(False))
        self.step_status.stepStarted()

        d = self.acquireLocks()
        d.addCallback(self._startStep_2)
        d.addErrback(self.failed)
        return self.deferred

    def acquireLocks(self, res=None):
        self._acquiringLock = None
        if not self.locks:
            return defer.succeed(None)
        if self.stopped:
            return defer.succeed(None)
        log.msg("acquireLocks(step %s, locks %s)" % (self, self.locks))
        for lock, access in self.locks:
            if not lock.isAvailable(access):
                self.step_status.setWaitingForLocks(True)
                log.msg("step %s waiting for lock %s" % (self, lock))
                d = lock.waitUntilMaybeAvailable(self, access)
                d.addCallback(self.acquireLocks)
                self._acquiringLock = (lock, access, d)
                return d
        # all locks are available, claim them all
        for lock, access in self.locks:
            lock.claim(self, access)
        self.step_status.setWaitingForLocks(False)
        return defer.succeed(None)

    def _startStep_2(self, res):
        if self.stopped:
            self.finished(EXCEPTION)
            return

        if self.progress:
            self.progress.start()

        if isinstance(self.doStepIf, bool):
            doStep = defer.succeed(self.doStepIf)
        else:
            doStep = defer.maybeDeferred(self.doStepIf, self)

        renderables = []
        accumulateClassList(self.__class__, 'renderables', renderables)

        for renderable in renderables:
            setattr(self, renderable, self.build.render(getattr(self, renderable)))

        doStep.addCallback(self._startStep_3)
        return doStep

    def _startStep_3(self, doStep):
        try:
            if doStep:
                if self.start() == SKIPPED:
                    doStep = False
        except:
            log.msg("BuildStep.startStep exception in .start")
            self.failed(Failure())

        if not doStep:
            self.step_status.setText(self.describe(True) + ['skipped'])
            self.step_status.setSkipped(True)
            # this return value from self.start is a shortcut to finishing
            # the step immediately; we skip calling finished() as
            # subclasses may have overridden that an expect it to be called
            # after start() (bug #837)
            reactor.callLater(0, self._finishFinished, SKIPPED)

    def start(self):
        """Begin the step. Override this method and add code to do local
        processing, fire off remote commands, etc.

        To spawn a command in the buildslave, create a RemoteCommand instance
        and run it with self.runCommand::

          c = RemoteCommandFoo(args)
          d = self.runCommand(c)
          d.addCallback(self.fooDone).addErrback(self.failed)

        As the step runs, it should send status information to the
        BuildStepStatus::

          self.step_status.setText(['compile', 'failed'])
          self.step_status.setText2(['4', 'warnings'])

        To have some code parse stdio (or other log stream) in realtime, add
        a LogObserver subclass. This observer can use self.step.setProgress()
        to provide better progress notification to the step.::

          self.addLogObserver('stdio', MyLogObserver())

        To add a LogFile, use self.addLog. Make sure it gets closed when it
        finishes. When giving a Logfile to a RemoteShellCommand, just ask it
        to close the log when the command completes::

          log = self.addLog('output')
          cmd = RemoteShellCommand(args)
          cmd.useLog(log, closeWhenFinished=True)

        You can also create complete Logfiles with generated text in a single
        step::

          self.addCompleteLog('warnings', text)

        When the step is done, it should call self.finished(result). 'result'
        will be provided to the L{buildbot.process.build.Build}, and should be
        one of the constants defined above: SUCCESS, WARNINGS, FAILURE, or
        SKIPPED.

        If the step encounters an exception, it should call self.failed(why).
        'why' should be a Failure object. This automatically fails the whole
        build with an exception. It is a good idea to add self.failed as an
        errback to any Deferreds you might obtain.

        If the step decides it does not need to be run, start() can return
        the constant SKIPPED. This fires the callback immediately: it is not
        necessary to call .finished yourself. This can also indicate to the
        status-reporting mechanism that this step should not be displayed.

        A step can be configured to only run under certain conditions.  To
        do this, set the step's doStepIf to a boolean value, or to a function
        that returns a boolean value.  If the value or function result is
        False, then the step will return SKIPPED without doing anything,
        otherwise the step will be executed normally.  If you set doStepIf
        to a function, that function should accept one parameter, which will
        be the Step object itself."""
        
        raise NotImplementedError("your subclass must implement this method")

    def interrupt(self, reason):
        """Halt the command, either because the user has decided to cancel
        the build ('reason' is a string), or because the slave has
        disconnected ('reason' is a ConnectionLost Failure). Any further
        local processing should be skipped, and the Step completed with an
        error status. The results text should say something useful like
        ['step', 'interrupted'] or ['remote', 'lost']"""
        self.stopped = True
        if self._acquiringLock:
            lock, access, d = self._acquiringLock
            lock.stopWaitingUntilAvailable(self, access, d)
            d.callback(None)

    def releaseLocks(self):
        log.msg("releaseLocks(%s): %s" % (self, self.locks))
        for lock, access in self.locks:
            if lock.isOwner(self, access):
                lock.release(self, access)
            else:
                # This should only happen if we've been interrupted
                assert self.stopped

    def finished(self, results):
        if self.stopped and results != RETRY:
            # We handle this specially because we don't care about
            # the return code of an interrupted command; we know
            # that this should just be exception due to interrupt
            # At the same time we must respect RETRY status because it's used
            # to retry interrupted build due to some other issues for example
            # due to slave lost
            results = EXCEPTION
            self.step_status.setText(self.describe(True) +
                                 ["interrupted"])
            self.step_status.setText2(["interrupted"])
        self._finishFinished(results)

    def _finishFinished(self, results):
        # internal function to indicate that this step is done; this is separated
        # from finished() so that subclasses can override finished()
        if self.progress:
            self.progress.finish()
        self.step_status.stepFinished(results)
        self.releaseLocks()
        self.deferred.callback(results)

    def failed(self, why):
        # if isinstance(why, pb.CopiedFailure): # a remote exception might
        # only have short traceback, so formatFailure is not as useful as
        # you'd like (no .frames, so no traceback is displayed)
        log.msg("BuildStep.failed, traceback follows")
        log.err(why)
        try:
            if self.progress:
                self.progress.finish()
            self.addHTMLLog("err.html", formatFailure(why))
            self.addCompleteLog("err.text", why.getTraceback())
            # could use why.getDetailedTraceback() for more information
            self.step_status.setText([self.name, "exception"])
            self.step_status.setText2([self.name])
            self.step_status.stepFinished(EXCEPTION)
        except:
            log.msg("exception during failure processing")
            log.err()
            # the progress stuff may still be whacked (the StepStatus may
            # think that it is still running), but the build overall will now
            # finish
        try:
            self.releaseLocks()
        except:
            log.msg("exception while releasing locks")
            log.err()

        log.msg("BuildStep.failed now firing callback")
        self.deferred.callback(EXCEPTION)

    # utility methods that BuildSteps may find useful

    def slaveVersion(self, command, oldversion=None):
        """Return the version number of the given slave command. For the
        commands defined in buildbot.slave.commands, this is the value of
        'cvs_ver' at the top of that file. Non-existent commands will return
        a value of None. Buildslaves running buildbot-0.5.0 or earlier did
        not respond to the version query: commands on those slaves will
        return a value of OLDVERSION, so you can distinguish between old
        buildslaves and missing commands.

        If you know that <=0.5.0 buildslaves have the command you want (CVS
        and SVN existed back then, but none of the other VC systems), then it
        makes sense to call this with oldversion='old'. If the command you
        want is newer than that, just leave oldversion= unspecified, and the
        command will return None for a buildslave that does not implement the
        command.
        """
        return self.build.getSlaveCommandVersion(command, oldversion)

    def slaveVersionIsOlderThan(self, command, minversion):
        sv = self.build.getSlaveCommandVersion(command, None)
        if sv is None:
            return True
        # the version we get back is a string form of the CVS version number
        # of the slave's buildbot/slave/commands.py, something like 1.39 .
        # This might change in the future (I might move away from CVS), but
        # if so I'll keep updating that string with suitably-comparable
        # values.
        if map(int, sv.split(".")) < map(int, minversion.split(".")):
            return True
        return False

    def getSlaveName(self):
        return self.build.getSlaveName()

    def addLog(self, name):
        loog = self.step_status.addLog(name)
        self._connectPendingLogObservers()
        return loog

    def getLog(self, name):
        for l in self.step_status.getLogs():
            if l.getName() == name:
                return l
        raise KeyError("no log named '%s'" % (name,))

    def addCompleteLog(self, name, text):
        log.msg("addCompleteLog(%s)" % name)
        loog = self.step_status.addLog(name)
        size = loog.chunkSize
        for start in range(0, len(text), size):
            loog.addStdout(text[start:start+size])
        loog.finish()
        self._connectPendingLogObservers()

    def addHTMLLog(self, name, html):
        log.msg("addHTMLLog(%s)" % name)
        self.step_status.addHTMLLog(name, html)
        self._connectPendingLogObservers()

    def addLogObserver(self, logname, observer):
        assert interfaces.ILogObserver.providedBy(observer)
        observer.setStep(self)
        self._pendingLogObservers.append((logname, observer))
        self._connectPendingLogObservers()

    def _connectPendingLogObservers(self):
        if not self._pendingLogObservers:
            return
        if not self.step_status:
            return
        current_logs = {}
        for loog in self.step_status.getLogs():
            current_logs[loog.getName()] = loog
        for logname, observer in self._pendingLogObservers[:]:
            if logname in current_logs:
                observer.setLog(current_logs[logname])
                self._pendingLogObservers.remove((logname, observer))

    def addURL(self, name, url):
        """Add a BuildStep URL to this step.

        An HREF to this URL will be added to any HTML representations of this
        step. This allows a step to provide links to external web pages,
        perhaps to provide detailed HTML code coverage results or other forms
        of build status.
        """
        self.step_status.addURL(name, url)

    def runCommand(self, c):
        c.buildslave = self.buildslave
        d = c.run(self, self.remote)
        return d


class OutputProgressObserver(LogObserver):
    length = 0

    def __init__(self, name):
        self.name = name

    def logChunk(self, build, step, log, channel, text):
        self.length += len(text)
        self.step.setProgress(self.name, self.length)

class LoggingBuildStep(BuildStep):
    """This is an abstract base class, suitable for inheritance by all
    BuildSteps that invoke RemoteCommands which emit stdout/stderr messages.
    """

    progressMetrics = ('output',)
    logfiles = {}

    parms = BuildStep.parms + ['logfiles', 'lazylogfiles', 'log_eval_func']
    cmd = None

    def __init__(self, logfiles={}, lazylogfiles=False, log_eval_func=None,
                 *args, **kwargs):
        BuildStep.__init__(self, *args, **kwargs)
        self.addFactoryArguments(logfiles=logfiles,
                                 lazylogfiles=lazylogfiles,
                                 log_eval_func=log_eval_func)

        if logfiles:
            assert type(logfiles) is type({}), \
                "the ShellCommand 'logfiles' parameter must be a dictionary"

        # merge a class-level 'logfiles' attribute with one passed in as an
        # argument
        self.logfiles = self.logfiles.copy()
        self.logfiles.update(logfiles)
        self.lazylogfiles = lazylogfiles
        assert not log_eval_func or callable(log_eval_func)
        self.log_eval_func = log_eval_func
        self.addLogObserver('stdio', OutputProgressObserver("output"))

    def addLogFile(self, logname, filename):
        """
        This allows to add logfiles after construction, but before calling
        startCommand().
        """
        self.logfiles[logname] = filename

    def startCommand(self, cmd, errorMessages=[]):
        """
        @param cmd: a suitable RemoteCommand which will be launched, with
                    all output being put into our self.stdio_log LogFile
        """
        log.msg("ShellCommand.startCommand(cmd=%s)" % (cmd,))
        log.msg("  cmd.args = %r" % (cmd.args))
        self.cmd = cmd # so we can interrupt it
        self.step_status.setText(self.describe(False))

        # stdio is the first log
        self.stdio_log = stdio_log = self.addLog("stdio")
        cmd.useLog(stdio_log, True)
        for em in errorMessages:
            stdio_log.addHeader(em)
            # TODO: consider setting up self.stdio_log earlier, and have the
            # code that passes in errorMessages instead call
            # self.stdio_log.addHeader() directly.

        # there might be other logs
        self.setupLogfiles(cmd, self.logfiles)

        d = self.runCommand(cmd) # might raise ConnectionLost
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addCallback(lambda res: self.createSummary(cmd.logs['stdio']))
        d.addCallback(lambda res: self.evaluateCommand(cmd)) # returns results
        def _gotResults(results):
            self.setStatus(cmd, results)
            return results
        d.addCallback(_gotResults) # returns results
        d.addCallbacks(self.finished, self.checkDisconnect)
        d.addErrback(self.failed)

    def setupLogfiles(self, cmd, logfiles):
        """Set up any additional logfiles= logs.

        @param cmd: the LoggedRemoteCommand to add additional logs to.

        @param logfiles: a dict of tuples (logname,remotefilename)
                         specifying additional logs to watch. (note:
                         the remotefilename component is currently
                         ignored)
        """
        for logname,remotefilename in logfiles.items():
            if self.lazylogfiles:
                # Ask LoggedRemoteCommand to watch a logfile, but only add
                # it when/if we see any data.
                #
                # The dummy default argument local_logname is a work-around for
                # Python name binding; default values are bound by value, but
                # captured variables in the body are bound by name.
                callback = lambda cmd_arg, local_logname=logname: self.addLog(local_logname)
                cmd.useLogDelayed(logname, callback, True)
            else:
                # tell the BuildStepStatus to add a LogFile
                newlog = self.addLog(logname)
                # and tell the LoggedRemoteCommand to feed it
                cmd.useLog(newlog, True)

    def interrupt(self, reason):
        # TODO: consider adding an INTERRUPTED or STOPPED status to use
        # instead of FAILURE, might make the text a bit more clear.
        # 'reason' can be a Failure, or text
        BuildStep.interrupt(self, reason)
        if self.step_status.isWaitingForLocks():
            self.addCompleteLog('interrupt while waiting for locks', str(reason))
        else:
            self.addCompleteLog('interrupt', str(reason))

        if self.cmd:
            d = self.cmd.interrupt(reason)
            return d

    def checkDisconnect(self, f):
        f.trap(error.ConnectionLost)
        self.step_status.setText(self.describe(True) +
                                 ["exception", "slave", "lost"])
        self.step_status.setText2(["exception", "slave", "lost"])
        return self.finished(RETRY)

    # to refine the status output, override one or more of the following
    # methods. Change as little as possible: start with the first ones on
    # this list and only proceed further if you have to    
    #
    # createSummary: add additional Logfiles with summarized results
    # evaluateCommand: decides whether the step was successful or not
    #
    # getText: create the final per-step text strings
    # describeText2: create the strings added to the overall build status
    #
    # getText2: only adds describeText2() when the step affects build status
    #
    # setStatus: handles all status updating

    # commandComplete is available for general-purpose post-completion work.
    # It is a good place to do one-time parsing of logfiles, counting
    # warnings and errors. It should probably stash such counts in places
    # like self.warnings so they can be picked up later by your getText
    # method.

    # TODO: most of this stuff should really be on BuildStep rather than
    # ShellCommand. That involves putting the status-setup stuff in
    # .finished, which would make it hard to turn off.

    def commandComplete(self, cmd):
        """This is a general-purpose hook method for subclasses. It will be
        called after the remote command has finished, but before any of the
        other hook functions are called."""
        pass

    def createSummary(self, log):
        """To create summary logs, do something like this:
        warnings = grep('^Warning:', log.getText())
        self.addCompleteLog('warnings', warnings)
        """
        pass

    def evaluateCommand(self, cmd):
        """Decide whether the command was SUCCESS, WARNINGS, or FAILURE.
        Override this to, say, declare WARNINGS if there is any stderr
        activity, or to say that rc!=0 is not actually an error."""

        if self.log_eval_func:
            return self.log_eval_func(cmd, self.step_status)
        if cmd.rc != 0:
            return FAILURE
        return SUCCESS

    def getText(self, cmd, results):
        if results == SUCCESS:
            return self.describe(True)
        elif results == WARNINGS:
            return self.describe(True) + ["warnings"]
        elif results == EXCEPTION:
            return self.describe(True) + ["exception"]
        else:
            return self.describe(True) + ["failed"]

    def getText2(self, cmd, results):
        """We have decided to add a short note about ourselves to the overall
        build description, probably because something went wrong. Return a
        short list of short strings. If your subclass counts test failures or
        warnings of some sort, this is a good place to announce the count."""
        # return ["%d warnings" % warningcount]
        # return ["%d tests" % len(failedTests)]
        return [self.name]

    def maybeGetText2(self, cmd, results):
        if results == SUCCESS:
            # successful steps do not add anything to the build's text
            pass
        elif results == WARNINGS:
            if (self.flunkOnWarnings or self.warnOnWarnings):
                # we're affecting the overall build, so tell them why
                return self.getText2(cmd, results)
        else:
            if (self.haltOnFailure or self.flunkOnFailure
                or self.warnOnFailure):
                # we're affecting the overall build, so tell them why
                return self.getText2(cmd, results)
        return []

    def setStatus(self, cmd, results):
        # this is good enough for most steps, but it can be overridden to
        # get more control over the displayed text
        self.step_status.setText(self.getText(cmd, results))
        self.step_status.setText2(self.maybeGetText2(cmd, results))


# Parses the logs for a list of regexs. Meant to be invoked like:
# regexes = ((re.compile(...), FAILURE), (re.compile(...), WARNINGS))
# self.addStep(ShellCommand,
#   command=...,
#   ...,
#   log_eval_func=lambda c,s: regex_log_evaluator(c, s, regexs)
# )
def regex_log_evaluator(cmd, step_status, regexes):
    worst = SUCCESS
    if cmd.rc != 0:
        worst = FAILURE
    for err, possible_status in regexes:
        # worst_status returns the worse of the two status' passed to it.
        # we won't be changing "worst" unless possible_status is worse than it,
        # so we don't even need to check the log if that's the case
        if worst_status(worst, possible_status) == possible_status:
            if isinstance(err, (basestring)):
                err = re.compile(".*%s.*" % err, re.DOTALL)
            for l in cmd.logs.values():
                if err.search(l.getText()):
                    worst = possible_status
    return worst


# (WithProperties used to be available in this module)
from buildbot.process.properties import WithProperties
_hush_pyflakes = [WithProperties]
del _hush_pyflakes

