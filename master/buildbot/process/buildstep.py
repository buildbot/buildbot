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
    step_status = None
    progress = None

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
        if self.progress:
            self.progress.setProgress(metric, value)

    @defer.inlineCallbacks
    def startStep(self, remote):
        self.remote = remote
        self.deferred = defer.Deferred()
        # convert all locks into their real form
        self.locks = [(self.build.builder.botmaster.getLockByID(access.lockid), access)
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

        # Set the step's text here so that the stepStarted notification sees
        # the correct description
        self.step_status.setText(self.describe(False))
        self.step_status.stepStarted()

        try:
            # set up locks
            yield self.acquireLocks()

            if self.stopped:
                self.finished(EXCEPTION)
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
                    result = yield defer.maybeDeferred(self.start)
                    if result == SKIPPED:
                        doStep = False
            except Exception:
                log.msg("BuildStep.startStep exception in .start")
                self.failed(Failure())

            if not doStep:
                self.step_status.setText(self.describe(True) + ['skipped'])
                self.step_status.setSkipped(True)
                # this return value from self.start is a shortcut to finishing
                # the step immediately; we skip calling finished() as
                # subclasses may have overridden that an expect it to be called
                # after start() (bug #837)
                eventually(self._finishFinished, SKIPPED)
        except Exception:
            self.failed(Failure())

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

    def start(self):
        raise NotImplementedError("your subclass must implement this method")

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
            self.step_status.setText(self.describe(True) +
                                     ["interrupted"])
            self.step_status.setText2(["interrupted"])
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

        self.step_status.stepFinished(results)
        self.step_status.setHidden(hidden)

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
            self.step_status.setText(self.describe(True) +
                                     ["exception", "slave", "lost"])
            self.step_status.setText2(["exception", "slave", "lost"])
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
            self.step_status.setText([self.name, "exception"])
            self.step_status.setText2([self.name])
            self.step_status.stepFinished(EXCEPTION)

            hidden = self._maybeEvaluate(self.hideStepIf, EXCEPTION, self)
            self.step_status.setHidden(hidden)
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
            loog.addStdout(text[start:start + size])
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
        self.step_status.addURL(name, url)

    def runCommand(self, c):
        self.cmd = c
        c.buildslave = self.buildslave
        d = c.run(self, self.remote)
        return d

    @staticmethod
    def _maybeEvaluate(value, *args, **kwargs):
        if callable(value):
            value = value(*args, **kwargs)
        return value

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
                callback = lambda cmd_arg, local_logname=logname: self.addLog(local_logname)
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
        if self.step_status.isWaitingForLocks():
            self.addCompleteLog('interrupt while waiting for locks', str(reason))
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
            return self.log_eval_func(cmd, self.step_status)
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
