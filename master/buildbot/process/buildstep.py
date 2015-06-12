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

from twisted.internet import defer
from twisted.internet import error
from twisted.python import components
from twisted.python import failure
from twisted.python import log
from twisted.python.failure import Failure
from twisted.python.reflect import accumulateClassList
from twisted.web.util import formatFailure
from zope.interface import implements

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot.process import logobserver
from buildbot.process import properties
from buildbot.process import remotecommand
from buildbot.status import progress
from buildbot.status.results import EXCEPTION
from buildbot.status.results import FAILURE
from buildbot.status.results import RETRY
from buildbot.status.results import SKIPPED
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS
from buildbot.status.results import worst_status
from buildbot.util import debounce
from buildbot.util import flatten
from buildbot.util.eventual import eventually


class BuildStepFailed(Exception):
    pass

# old import paths for these classes
RemoteCommand = remotecommand.RemoteCommand
LoggedRemoteCommand = remotecommand.LoggedRemoteCommand
RemoteShellCommand = remotecommand.RemoteShellCommand
LogObserver = logobserver.LogObserver
LogLineObserver = logobserver.LogLineObserver
OutputProgressObserver = logobserver.OutputProgressObserver
_hush_pyflakes = [
    RemoteCommand, LoggedRemoteCommand, RemoteShellCommand,
    LogObserver, LogLineObserver, OutputProgressObserver]


class _BuildStepFactory(util.ComparableMixin):

    """
    This is a wrapper to record the arguments passed to as BuildStep subclass.
    We use an instance of this class, rather than a closure mostly to make it
    easier to test that the right factories are getting created.
    """
    compare_attrs = ['factory', 'args', 'kwargs']
    implements(interfaces.IBuildStepFactory)

    def __init__(self, factory, *args, **kwargs):
        self.factory = factory
        self.args = args
        self.kwargs = kwargs

    def buildStep(self):
        try:
            return self.factory(*self.args, **self.kwargs)
        except Exception:
            log.msg("error while creating step, factory=%s, args=%s, kwargs=%s"
                    % (self.factory, self.args, self.kwargs))
            raise


class BuildStep(object, properties.PropertiesMixin):

    implements(interfaces.IBuildStep)

    haltOnFailure = False
    flunkOnWarnings = False
    flunkOnFailure = False
    warnOnWarnings = False
    warnOnFailure = False
    alwaysRun = False
    doStepIf = True
    hideStepIf = False

    # properties set on a build step are, by nature, always runtime properties
    set_runtime_properties = True

    renderables = [
        'haltOnFailure',
        'flunkOnWarnings',
        'flunkOnFailure',
        'warnOnWarnings',
        'warnOnFailure',
        'alwaysRun',
        'doStepIf',
        'hideStepIf',
    ]

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
             'useProgress',
             'doStepIf',
             'hideStepIf',
             'description',
             'descriptionDone',
             'descriptionSuffix',
             ]

    name = "generic"
    description = None  # set this to a list of short strings to override
    descriptionDone = None  # alternate description when the step is complete
    descriptionSuffix = None  # extra information to append to suffix
    locks = []
    progressMetrics = ()  # 'time' is implicit
    useProgress = True  # set to False if step is really unpredictable
    build = None
    buildslave = None
    progress = None
    cmd = None
    _step_status = None

    def __init__(self, **kwargs):
        for p in self.__class__.parms:
            if p in kwargs:
                setattr(self, p, kwargs[p])
                del kwargs[p]
        if kwargs:
            config.error("%s.__init__ got unexpected keyword argument(s) %s"
                         % (self.__class__, kwargs.keys()))
        self._pendingLogObservers = []

        if not isinstance(self.name, str):
            config.error("BuildStep name must be a string: %r" % (self.name,))

        self._acquiringLock = None
        self.stopped = False
        self.master = None

    def __new__(klass, *args, **kwargs):
        self = object.__new__(klass)
        self._factory = _BuildStepFactory(klass, *args, **kwargs)
        return self

    def _describe(self, done=False):
        if self.descriptionDone and done:
            return self.descriptionDone
        elif self.description:
            return self.description
        return [self.name]

    def describe(self, done=False):
        desc = self._describe(done)
        if self.descriptionSuffix:
            desc = desc + self.descriptionSuffix
        return desc

    def setBuild(self, build):
        self.build = build
        self.master = self.build.master

    def setBuildSlave(self, buildslave):
        self.buildslave = buildslave

    def setDefaultWorkdir(self, workdir):
        pass

    def addFactoryArguments(self, **kwargs):
        # this is here for backwards compatibility
        pass

    def _getStepFactory(self):
        return self._factory

    @property
    def step_status(self):
        assert not self.isNewStyle(
        ), "self.step_status is not available in new-style steps"
        return self._step_status

    def setStepStatus(self, step_status):
        self._step_status = step_status

    def setupProgress(self):
        if self.useProgress:
            sp = progress.StepProgress(self.name, self.progressMetrics)
            self.progress = sp
            self._step_status.setProgress(sp)
            return sp
        return None

    def setProgress(self, metric, value):
        if self.progress:
            self.progress.setProgress(metric, value)

    def getCurrentSummary(self):
        return u'running'

    def getResultSummary(self):
        return {}

    @debounce.method(wait=1)
    @defer.inlineCallbacks
    def updateSummary(self):
        assert self.isNewStyle(), "updateSummary is a new-style step method"
        if self._step_status.isFinished():
            summary = yield self.getResultSummary()
            if not isinstance(summary, dict):
                raise TypeError('getResultSummary must return a dictionary')
        else:
            summary = yield self.getCurrentSummary()
            if not isinstance(summary, dict):
                raise TypeError('getCurrentSummary must return a dictionary')

        stepResult = summary.get('step', u'finished')
        if not isinstance(stepResult, unicode):
            raise TypeError("step summary must be unicode")
        self._step_status.setText([stepResult])

        if self._step_status.isFinished():
            buildResult = summary.get('build', None)
            if buildResult and not isinstance(buildResult, unicode):
                raise TypeError("build result must be unicode")
            self._step_status.setText2([buildResult] if buildResult else [])

    @defer.inlineCallbacks
    def startStep(self, remote):
        self.remote = remote
        isNew = self.isNewStyle()

        old_finished = self.finished
        old_failed = self.failed
        if isNew:
            def nope(*args, **kwargs):
                raise AssertionError("new-style steps must not call "
                                     "this method")
            self.finished = nope
            self.failed = nope

        # convert all locks into their real form
        self.locks = [(self.build.builder.botmaster.getLockFromLockAccess(access), access)
                      for access in self.locks]
        # then narrow SlaveLocks down to the slave that this build is being
        # run on
        self.locks = [(l.getLock(self.build.slavebuilder.slave), la)
                      for l, la in self.locks]

        for l, la in self.locks:
            if l in self.build.locks:
                log.msg("Hey, lock %s is claimed by both a Step (%s) and the"
                        " parent Build (%s)" % (l, self, self.build))
                raise RuntimeError("lock claimed by both Step and Build")

        self.deferred = defer.Deferred()

        # Set the step's text here so that the stepStarted notification sees
        # the correct description
        self._step_status.setText(self.describe(False))
        self._step_status.stepStarted()

        try:
            # set up locks
            yield self.acquireLocks()

            if self.stopped:
                old_finished(EXCEPTION)
                defer.returnValue((yield self.deferred))

            # ste up progress
            if self.progress:
                self.progress.start()

            # check doStepIf
            if isinstance(self.doStepIf, bool):
                doStep = self.doStepIf
            else:
                doStep = yield self.doStepIf(self)

            # render renderables in parallel
            renderables = []
            accumulateClassList(self.__class__, 'renderables', renderables)

            def setRenderable(res, attr):
                setattr(self, attr, res)

            dl = []
            for renderable in renderables:
                d = self.build.render(getattr(self, renderable))
                d.addCallback(setRenderable, renderable)
                dl.append(d)
            yield defer.gatherResults(dl)

            try:
                if doStep:
                    if isNew:
                        result = yield self.run()
                        assert isinstance(result, int), \
                            "run must return an integer (via Deferred)"
                        old_finished(result)
                    else:
                        result = yield self.start()
                    if result == SKIPPED:
                        doStep = False
            except Exception:
                log.msg("BuildStep.startStep exception in .start")
                self.finished = old_finished
                old_failed(Failure())

            if not doStep:
                self._step_status.setText(self.describe(True) + ['skipped'])
                self._step_status.setSkipped(True)
                # this return value from self.start is a shortcut to finishing
                # the step immediately; we skip calling finished() as
                # subclasses may have overridden that an expect it to be called
                # after start() (bug #837)
                eventually(self._finishFinished, SKIPPED)
        except Exception:
            self.finished = old_finished
            old_failed(Failure())

        # and finally, wait for self.deferred to get triggered and return its
        # value
        defer.returnValue((yield self.deferred))

    def acquireLocks(self, res=None):
        self._acquiringLock = None
        if not self.locks:
            return defer.succeed(None)
        if self.stopped:
            return defer.succeed(None)
        log.msg("acquireLocks(step %s, locks %s)" % (self, self.locks))
        for lock, access in self.locks:
            if not lock.isAvailable(self, access):
                self._step_status.setWaitingForLocks(True)
                log.msg("step %s waiting for lock %s" % (self, lock))
                d = lock.waitUntilMaybeAvailable(self, access)
                d.addCallback(self.acquireLocks)
                self._acquiringLock = (lock, access, d)
                return d
        # all locks are available, claim them all
        for lock, access in self.locks:
            lock.claim(self, access)
        self._step_status.setWaitingForLocks(False)
        return defer.succeed(None)

    def isNewStyle(self):
        # **temporary** method until new-style steps are the only supported style
        return self.run.im_func is not BuildStep.run.im_func

    def run(self):
        # new-style steps override this, by definition.
        # old-style steps don't call it.
        raise NotImplementedError

    def start(self):
        raise NotImplementedError("your subclass must implement run()")

    def interrupt(self, reason):
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
            if results != RETRY:
                results = EXCEPTION
            self._step_status.setText(self.describe(True) +
                                      ["interrupted"])
            self._step_status.setText2(["interrupted"])
        self._finishFinished(results)

    def _finishFinished(self, results):
        # internal function to indicate that this step is done; this is separated
        # from finished() so that subclasses can override finished()
        if self.progress:
            self.progress.finish()

        try:
            hidden = self._maybeEvaluate(self.hideStepIf, results, self)
        except Exception:
            why = Failure()
            self.addHTMLLog("err.html", formatFailure(why))
            self.addCompleteLog("err.text", why.getTraceback())
            results = EXCEPTION
            hidden = False

        self._step_status.stepFinished(results)
        self._step_status.setHidden(hidden)

        self.releaseLocks()
        self.deferred.callback(results)

    def failed(self, why):
        # This can either be a BuildStepFailed exception/failure, meaning we
        # should call self.finished, or it can be a real exception, which should
        # be recorded as such.
        if why.check(BuildStepFailed):
            self.finished(FAILURE)
            return
        # However, in the case of losing the connection to a slave, we want to
        # finish with a RETRY.
        if why.check(error.ConnectionLost):
            self._step_status.setText(self.describe(True) +
                                      ["exception", "slave", "lost"])
            self._step_status.setText2(["exception", "slave", "lost"])
            self.finished(RETRY)
            return

        log.err(why, "BuildStep.failed; traceback follows")
        try:
            if self.progress:
                self.progress.finish()
            try:
                self.addCompleteLog("err.text", why.getTraceback())
                self.addHTMLLog("err.html", formatFailure(why))
            except Exception:
                log.err(Failure(), "error while formatting exceptions")

            # could use why.getDetailedTraceback() for more information
            self._step_status.setText([self.name, "exception"])
            self._step_status.setText2([self.name])
            self._step_status.stepFinished(EXCEPTION)

            hidden = self._maybeEvaluate(self.hideStepIf, EXCEPTION, self)
            self._step_status.setHidden(hidden)
        except Exception:
            log.err(Failure(), "exception during failure processing")
            # the progress stuff may still be whacked (the StepStatus may
            # think that it is still running), but the build overall will now
            # finish

        try:
            self.releaseLocks()
        except Exception:
            log.err(Failure(), "exception while releasing locks")

        log.msg("BuildStep.failed now firing callback")
        self.deferred.callback(EXCEPTION)

    # utility methods that BuildSteps may find useful

    def slaveVersion(self, command, oldversion=None):
        return self.build.getSlaveCommandVersion(command, oldversion)

    def slaveVersionIsOlderThan(self, command, minversion):
        sv = self.build.getSlaveCommandVersion(command, None)
        if sv is None:
            return True
        if map(int, sv.split(".")) < map(int, minversion.split(".")):
            return True
        return False

    def getSlaveName(self):
        return self.build.getSlaveName()

    def addLog(self, name):
        loog = self._step_status.addLog(name)
        self._connectPendingLogObservers()
        if self.isNewStyle():
            loog._isNewStyle = True
            return defer.succeed(loog)
        else:
            return loog

    def getLog(self, name):
        for l in self._step_status.getLogs():
            if l.getName() == name:
                return l
        raise KeyError("no log named '%s'" % (name,))

    def addCompleteLog(self, name, text):
        log.msg("addCompleteLog(%s)" % name)
        loog = self._step_status.addLog(name)
        size = loog.chunkSize
        for start in range(0, len(text), size):
            loog.addStdout(text[start:start + size])
        loog.finish()
        self._connectPendingLogObservers()
        return defer.succeed(None)

    def addHTMLLog(self, name, html):
        log.msg("addHTMLLog(%s)" % name)
        self._step_status.addHTMLLog(name, html)
        self._connectPendingLogObservers()
        return defer.succeed(None)

    def addLogObserver(self, logname, observer):
        assert interfaces.ILogObserver.providedBy(observer)
        observer.setStep(self)
        self._pendingLogObservers.append((logname, observer))
        self._connectPendingLogObservers()

    def _connectPendingLogObservers(self):
        if not self._pendingLogObservers:
            return
        if not self._step_status:
            return
        current_logs = {}
        for loog in self._step_status.getLogs():
            current_logs[loog.getName()] = loog
        for logname, observer in self._pendingLogObservers[:]:
            if logname in current_logs:
                observer.setLog(current_logs[logname])
                self._pendingLogObservers.remove((logname, observer))

    def addURL(self, name, url):
        self._step_status.addURL(name, url)
        return defer.succeed(None)

    @defer.inlineCallbacks
    def runCommand(self, command):
        self.cmd = command
        command.buildslave = self.buildslave
        try:
            res = yield command.run(self, self.remote)
        finally:
            self.cmd = None
        defer.returnValue(res)

    @staticmethod
    def _maybeEvaluate(value, *args, **kwargs):
        if callable(value):
            value = value(*args, **kwargs)
        return value

    def hasStatistic(self, name):
        return self._step_status.hasStatistic(name)

    def getStatistic(self, name, default=None):
        return self._step_status.getStatistic(name, default)

    def getStatistics(self):
        return self._step_status.getStatistics()

    def setStatistic(self, name, value):
        return self._step_status.setStatistic(name, value)


components.registerAdapter(
    BuildStep._getStepFactory,
    BuildStep, interfaces.IBuildStepFactory)
components.registerAdapter(
    lambda step: interfaces.IProperties(step.build),
    BuildStep, interfaces.IProperties)


class LoggingBuildStep(BuildStep):

    progressMetrics = ('output',)
    logfiles = {}

    parms = BuildStep.parms + ['logfiles', 'lazylogfiles', 'log_eval_func']
    cmd = None

    renderables = ['logfiles', 'lazylogfiles']

    def __init__(self, logfiles={}, lazylogfiles=False, log_eval_func=None,
                 *args, **kwargs):
        BuildStep.__init__(self, *args, **kwargs)

        if logfiles and not isinstance(logfiles, dict):
            config.error(
                "the ShellCommand 'logfiles' parameter must be a dictionary")

        # merge a class-level 'logfiles' attribute with one passed in as an
        # argument
        self.logfiles = self.logfiles.copy()
        self.logfiles.update(logfiles)
        self.lazylogfiles = lazylogfiles
        if log_eval_func and not callable(log_eval_func):
            config.error(
                "the 'log_eval_func' paramater must be a callable")
        self.log_eval_func = log_eval_func
        self.addLogObserver('stdio', OutputProgressObserver("output"))

    def addLogFile(self, logname, filename):
        self.logfiles[logname] = filename

    def buildCommandKwargs(self):
        kwargs = dict()
        kwargs['logfiles'] = self.logfiles
        return kwargs

    def startCommand(self, cmd, errorMessages=[]):
        """
        @param cmd: a suitable RemoteCommand which will be launched, with
                    all output being put into our self.stdio_log LogFile
        """
        log.msg("ShellCommand.startCommand(cmd=%s)" % (cmd,))
        log.msg("  cmd.args = %r" % (cmd.args))
        self.cmd = cmd  # so we can interrupt it
        self._step_status.setText(self.describe(False))

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

        d = self.runCommand(cmd)  # might raise ConnectionLost
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addCallback(lambda res: self.createSummary(cmd.logs['stdio']))
        d.addCallback(lambda res: self.evaluateCommand(cmd))  # returns results

        def _gotResults(results):
            self.setStatus(cmd, results)
            return results
        d.addCallback(_gotResults)  # returns results
        d.addCallback(self.finished)
        d.addErrback(self.failed)

    def setupLogfiles(self, cmd, logfiles):
        for logname, remotefilename in logfiles.items():
            if self.lazylogfiles:
                # Ask RemoteCommand to watch a logfile, but only add
                # it when/if we see any data.
                #
                # The dummy default argument local_logname is a work-around for
                # Python name binding; default values are bound by value, but
                # captured variables in the body are bound by name.
                callback = lambda cmd_arg, local_logname=logname: self.addLog(
                    local_logname)
                cmd.useLogDelayed(logname, callback, True)
            else:
                # tell the BuildStepStatus to add a LogFile
                newlog = self.addLog(logname)
                # and tell the RemoteCommand to feed it
                cmd.useLog(newlog, True)

    def interrupt(self, reason):
        # TODO: consider adding an INTERRUPTED or STOPPED status to use
        # instead of FAILURE, might make the text a bit more clear.
        # 'reason' can be a Failure, or text
        BuildStep.interrupt(self, reason)
        if self._step_status.isWaitingForLocks():
            self.addCompleteLog(
                'interrupt while waiting for locks', str(reason))
        else:
            self.addCompleteLog('interrupt', str(reason))

        if self.cmd:
            d = self.cmd.interrupt(reason)
            d.addErrback(log.err, 'while interrupting command')

    def checkDisconnect(self, f):
        # this is now handled by self.failed
        log.msg("WARNING: step %s uses deprecated checkDisconnect method")
        return f

    def commandComplete(self, cmd):
        pass

    def createSummary(self, stdio):
        pass

    def evaluateCommand(self, cmd):
        if self.log_eval_func:
            return self.log_eval_func(cmd, self._step_status)
        return cmd.results()

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
        self._step_status.setText(self.getText(cmd, results))
        self._step_status.setText2(self.maybeGetText2(cmd, results))


class CommandMixin(object):

    @defer.inlineCallbacks
    def _runRemoteCommand(self, cmd, abandonOnFailure, args, makeResult=None):
        cmd = remotecommand.RemoteCommand(cmd, args)
        try:
            log = self.getLog('stdio')
        except Exception:
            log = yield self.addLog('stdio')
        cmd.useLog(log, False)
        yield self.runCommand(cmd)
        if abandonOnFailure and cmd.didFail():
            raise BuildStepFailed()
        if makeResult:
            defer.returnValue(makeResult(cmd))
        else:
            defer.returnValue(not cmd.didFail())

    def runRmdir(self, dir, log=None, abandonOnFailure=True):
        return self._runRemoteCommand('rmdir', abandonOnFailure,
                                      {'dir': dir, 'logEnviron': False})

    def pathExists(self, path, log=None):
        return self._runRemoteCommand('stat', False,
                                      {'file': path, 'logEnviron': False})

    def runMkdir(self, dir, log=None, abandonOnFailure=True):
        return self._runRemoteCommand('mkdir', abandonOnFailure,
                                      {'dir': dir, 'logEnviron': False})

    def glob(self, glob):
        return self._runRemoteCommand(
            'glob', True, {'glob': glob, 'logEnviron': False},
            makeResult=lambda cmd: cmd.updates['files'][0])


class ShellMixin(object):

    command = None
    workdir = None
    env = {}
    want_stdout = True
    want_stderr = True
    usePTY = 'slave-config'
    logfiles = {}
    lazylogfiles = {}
    timeout = 1200
    maxTime = None
    logEnviron = True
    interruptSignal = 'KILL'
    sigtermTime = None
    initialStdin = None
    decodeRC = {0: SUCCESS}

    _shellMixinArgs = [
        'command',
        'workdir',
        'env',
        'want_stdout',
        'want_stderr',
        'usePTY',
        'logfiles',
        'lazylogfiles',
        'timeout',
        'maxTime',
        'logEnviron',
        'interruptSignal',
        'sigtermTime',
        'initialStdin',
        'decodeRC',
    ]
    renderables = _shellMixinArgs

    def setupShellMixin(self, constructorArgs, prohibitArgs=[]):
        constructorArgs = constructorArgs.copy()

        def bad(arg):
            config.error("invalid %s argument %s" %
                         (self.__class__.__name__, arg))
        for arg in self._shellMixinArgs:
            if arg not in constructorArgs:
                continue
            if arg in prohibitArgs:
                bad(arg)
            else:
                setattr(self, arg, constructorArgs[arg])
            del constructorArgs[arg]
        for arg in constructorArgs:
            if arg not in BuildStep.parms:
                bad(arg)
                del constructorArgs[arg]
        return constructorArgs

    @defer.inlineCallbacks
    def makeRemoteShellCommand(self, collectStdout=False, collectStderr=False,
                               stdioLogName='stdio',
                               **overrides):
        kwargs = dict([(arg, getattr(self, arg))
                       for arg in self._shellMixinArgs])
        kwargs.update(overrides)
        stdio = None
        if stdioLogName is not None:
            # Reuse an existing log if possible; otherwise, create one.
            try:
                stdio = yield self.getLog(stdioLogName)
            except KeyError:
                stdio = yield self.addLog(stdioLogName)

        kwargs['command'] = flatten(kwargs['command'], (list, tuple))

        # check for the usePTY flag
        if kwargs['usePTY'] != 'slave-config':
            if self.slaveVersionIsOlderThan("shell", "2.7"):
                if stdio is not None:
                    yield stdio.addHeader(
                        "NOTE: slave does not allow master to override usePTY\n")
                del kwargs['usePTY']

        # check for the interruptSignal flag
        if kwargs["interruptSignal"] and self.slaveVersionIsOlderThan("shell", "2.15"):
            if stdio is not None:
                yield stdio.addHeader(
                    "NOTE: slave does not allow master to specify interruptSignal\n")
            del kwargs['interruptSignal']

        # lazylogfiles are handled below
        del kwargs['lazylogfiles']

        # merge the builder's environment with that supplied here
        builderEnv = self.build.builder.config.env
        kwargs['env'] = yield self.build.render(builderEnv)
        kwargs['env'].update(self.env)
        kwargs['stdioLogName'] = stdioLogName
        # default the workdir appropriately
        if not kwargs.get('workdir') and not self.workdir:
            if callable(self.build.workdir):
                kwargs['workdir'] = self.build.workdir(self.build.sources)
            else:
                kwargs['workdir'] = self.build.workdir

        # the rest of the args go to RemoteShellCommand
        cmd = remotecommand.RemoteShellCommand(
            collectStdout=collectStdout,
            collectStderr=collectStderr,
            **kwargs
        )

        # set up logging
        if stdio is not None:
            cmd.useLog(stdio, False)
        for logname, remotefilename in self.logfiles.items():
            if self.lazylogfiles:
                # it's OK if this does, or does not, return a Deferred
                callback = lambda cmd_arg, logname=logname: self.addLog(
                    logname)
                cmd.useLogDelayed(logname, callback, True)
            else:
                # tell the BuildStepStatus to add a LogFile
                newlog = yield self.addLog(logname)
                # and tell the RemoteCommand to feed it
                cmd.useLog(newlog, False)

        defer.returnValue(cmd)

    def _describe(self, done=False):
        try:
            if done and self.descriptionDone is not None:
                return self.descriptionDone
            if self.description is not None:
                return self.description

            # if self.cmd is set, then use the RemoteCommand's info
            if self.cmd:
                command = self.command.command
            # otherwise, if we were configured with a command, use that
            elif self.command:
                command = self.command
            else:
                return super(ShellMixin, self)._describe(done)

            words = command
            if isinstance(words, (str, unicode)):
                words = words.split()

            try:
                len(words)
            except (AttributeError, TypeError):
                # WithProperties and Property don't have __len__
                # For old-style classes instances AttributeError raised,
                # for new-style classes instances - TypeError.
                return super(ShellMixin, self)._describe(done)

            # flatten any nested lists
            words = flatten(words, (list, tuple))

            # strip instances and other detritus (which can happen if a
            # description is requested before rendering)
            words = [w for w in words if isinstance(w, (str, unicode))]

            if len(words) < 1:
                return super(ShellMixin, self)._describe(done)
            if len(words) == 1:
                return ["'%s'" % words[0]]
            if len(words) == 2:
                return ["'%s" % words[0], "%s'" % words[1]]
            return ["'%s" % words[0], "%s" % words[1], "...'"]

        except Exception:
            log.err(failure.Failure(), "Error describing step")
            return super(ShellMixin, self)._describe(done)

# Parses the logs for a list of regexs. Meant to be invoked like:
# regexes = ((re.compile(...), FAILURE), (re.compile(...), WARNINGS))
# self.addStep(ShellCommand,
#   command=...,
#   ...,
#   log_eval_func=lambda c,s: regex_log_evaluator(c, s, regexs)
# )


def regex_log_evaluator(cmd, step_status, regexes):
    worst = cmd.results()
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
