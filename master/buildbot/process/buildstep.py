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

try:
    import cStringIO as StringIO
    assert StringIO
except ImportError:
    import StringIO
import re

from twisted.internet import defer
from twisted.internet import error
from twisted.python import components
from twisted.python import failure
from twisted.python import log
from twisted.python import util as twutil
from twisted.python.failure import Failure
from twisted.python.reflect import accumulateClassList
from twisted.web.util import formatFailure
from zope.interface import implements

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot.process import log as plog
from buildbot.process import logobserver
from buildbot.process import properties
from buildbot.process import remotecommand
from buildbot.status import progress
from buildbot.status import results
from buildbot.status.logfile import HEADER
from buildbot.status.logfile import STDERR
from buildbot.status.logfile import STDOUT
from buildbot.status.results import CANCELLED
from buildbot.status.results import EXCEPTION
from buildbot.status.results import FAILURE
from buildbot.status.results import RETRY
from buildbot.status.results import SKIPPED
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS
from buildbot.status.results import worst_status
from buildbot.util import debounce
from buildbot.util import flatten


class BuildStepFailed(Exception):
    pass


class BuildStepCancelled(Exception):
    # used internally for signalling
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


def _maybeUnhandled(fn):
    def wrap(self, *args, **kwargs):
        d = fn(self, *args, **kwargs)
        if self._start_unhandled_deferreds is not None:
            self._start_unhandled_deferreds.append(d)
        return d
    wrap.func_original = fn
    twutil.mergeFunctionMetadata(fn, wrap)
    return wrap


class SyncLogFileWrapper(logobserver.LogObserver):

    # A temporary wrapper around process.log.Log to emulate *synchronous*
    # writes to the logfile by handling the Deferred from each add* operation
    # as part of the step's _start_unhandled_deferreds.  This has to handle
    # the tricky case of adding data to a log *before* addLog has returned!
    # this also adds the read-only methods such as getText

    def __init__(self, step, name, addLogDeferred):
        self.step = step
        self.name = name
        self.delayedOperations = []
        self.asyncLogfile = None
        self.chunks = []
        self.finished = False
        self.finishDeferreds = []

        @addLogDeferred.addCallback
        def gotAsync(log):
            self.asyncLogfile = log
            self._catchup()
            return log

        # run _catchup even if there's an error; it will helpfully generate
        # a whole bunch more!
        @addLogDeferred.addErrback
        def problem(f):
            self._catchup()
            return f

    def _catchup(self):
        if not self.asyncLogfile or not self.delayedOperations:
            return
        op = self.delayedOperations.pop(0)

        try:
            d = defer.maybeDeferred(op)
        except Exception:
            d = defer.fail(failure.Failure())

        @d.addBoth
        def next(x):
            self._catchup()
            return x
        self.step._start_unhandled_deferreds.append(d)

    def _delay(self, op):
        self.delayedOperations.append(op)
        if len(self.delayedOperations) == 1:
            self._catchup()

    def _maybeFinished(self):
        if self.finished and self.finishDeferreds:
            pending = self.finishDeferreds
            self.finishDeferreds = []
            for d in pending:
                d.callback(self)

    # write methods

    def addStdout(self, data):
        self.chunks.append((STDOUT, data))
        self._delay(lambda: self.asyncLogfile.addStdout(data))

    def addStderr(self, data):
        self.chunks.append((STDERR, data))
        self._delay(lambda: self.asyncLogfile.addStderr(data))

    def addHeader(self, data):
        self.chunks.append((HEADER, data))
        self._delay(lambda: self.asyncLogfile.addHeader(data))

    def finish(self):
        self.finished = True
        self._maybeFinished()
        self._delay(lambda: self.asyncLogfile.finish())

    def unwrap(self):
        d = defer.Deferred()
        self._delay(lambda: d.callback(self.asyncLogfile))
        return d

    # read-only methods

    def getName(self):
        return self.name

    def getText(self):
        return "".join(self.getChunks([STDOUT, STDERR], onlyText=True))

    def readlines(self):
        alltext = "".join(self.getChunks([STDOUT], onlyText=True))
        io = StringIO.StringIO(alltext)
        return io.readlines()

    def getChunks(self, channels=[], onlyText=False):
        chunks = self.chunks
        if channels:
            channels = set(channels)
            chunks = ((c, t) for (c, t) in chunks if c in channels)
        if onlyText:
            chunks = (t for (c, t) in chunks)
        return chunks

    def isFinished(self):
        return self.finished

    def waitUntilFinished(self):
        d = defer.Deferred()
        self.finishDefereds.append(d)
        self._maybeFinished()


class BuildStep(results.ResultComputingConfigMixin,
                properties.PropertiesMixin):

    alwaysRun = False
    doStepIf = True
    hideStepIf = False

    # properties set on a build step are, by nature, always runtime properties
    set_runtime_properties = True

    renderables = results.ResultComputingConfigMixin.resultConfig + [
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
             'logEncoding',
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
    step_status = None
    progress = None
    logEncoding = None
    cmd = None
    rendered = False  # true if attributes are rendered

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
        self.statistics = {}
        self.logs = {}
        self._running = False

        self._start_unhandled_deferreds = None

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
        assert(self.rendered)
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
            # XXX this uses self.name, but the name may change when the
            # step is started..
            sp = progress.StepProgress(self.name, self.progressMetrics)
            self.progress = sp
            self.step_status.setProgress(sp)
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
        if not self._running:
            resultSummary = yield self.getResultSummary()
            stepResult = resultSummary.get('step', u'finished')
            assert isinstance(stepResult, unicode), \
                "step result must be unicode"
            yield self.master.data.updates.setStepStateStrings(self.stepid,
                                                               [stepResult])
            buildResult = resultSummary.get('build', None)
            assert buildResult is None or isinstance(buildResult, unicode), \
                "build result must be unicode"
            self.step_status.setText([stepResult])
            self.step_status.setText2([buildResult] if buildResult else [])
        else:
            stepSummary = yield self.getCurrentSummary()
            assert isinstance(stepSummary, unicode), \
                "step summary must be unicode"
            yield self.master.data.updates.setStepStateStrings(self.stepid,
                                                               [stepSummary])
            self.step_status.setText([stepSummary])

    @defer.inlineCallbacks
    def startStep(self, remote):
        self.remote = remote

        # create and start the step, noting that the name may be altered to
        # ensure uniqueness
        # XXX self.number != self.step_status.number..
        self.stepid, self.number, self.name = yield self.master.data.updates.newStep(
            buildid=self.build.buildid,
            name=util.ascii2unicode(self.name))
        yield self.master.data.updates.startStep(self.stepid)

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

        self.step_status.stepStarted()

        try:
            # set up locks
            yield self.acquireLocks()

            if self.stopped:
                raise BuildStepCancelled

            # set up progress
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
            self.rendered = True
            # we describe ourselves only when renderables are interpolated
            self.updateSummary()

            # run -- or skip -- the step
            if doStep:
                try:
                    self._running = True
                    results = yield self.run()
                finally:
                    self._running = False
            else:
                self.step_status.setSkipped(True)
                results = SKIPPED

        except BuildStepCancelled:
            results = CANCELLED

        except BuildStepFailed:
            results = FAILURE
            # fall through to the end

        except error.ConnectionLost:
            results = RETRY

        except Exception:
            why = Failure()
            log.err(why, "BuildStep.failed; traceback follows")
            yield self.addLogWithFailure(why)

            results = EXCEPTION

        if self.stopped and results != RETRY:
            # We handle this specially because we don't care about
            # the return code of an interrupted command; we know
            # that this should just be exception due to interrupt
            # At the same time we must respect RETRY status because it's used
            # to retry interrupted build due to some other issues for example
            # due to slave lost
            if results != CANCELLED:
                results = EXCEPTION

        # update the summary one last time, make sure that completes,
        # and then don't update it any more.
        self.updateSummary()
        yield self.updateSummary.stop()

        if self.progress:
            self.progress.finish()

        self.step_status.stepFinished(results)

        yield self.master.data.updates.finishStep(self.stepid, results)

        hidden = self.hideStepIf
        if callable(hidden):
            try:
                hidden = hidden(results, self)
            except Exception:
                results = EXCEPTION
                hidden = False
        self.step_status.setHidden(hidden)

        self.releaseLocks()

        defer.returnValue(results)

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

    @defer.inlineCallbacks
    def run(self):
        self._start_deferred = defer.Deferred()
        unhandled = self._start_unhandled_deferreds = []
        try:
            # here's where we set things up for backward compatibility for
            # old-style tests, using monkey patches so that new-style tests
            # aren't bothered by any of this equipment

            # monkey-patch self.step_status.{setText,setText2} back into
            # existence for old steps; when these write to the data API,
            # the monkey patches will stash their deferreds on the unhandled
            # list
            self.step_status.setText = self.step_status.old_setText
            self.step_status.setText2 = self.step_status.old_setText2

            # monkey-patch in support for old statistics functions
            self.step_status.setStatistic = self.setStatistic
            self.step_status.getStatistic = self.getStatistic
            self.step_status.hasStatistic = self.hasStatistic

            # monkey-patch an addLog that returns an write-only, sync log
            self.addLog = self.addLog_oldStyle
            self._logFileWrappers = {}

            # and a getLog that returns a read-only, sync log, captured by
            # LogObservers installed by addLog_oldStyle
            self.getLog = self.getLog_oldStyle

            results = yield self.start()
            if results == SKIPPED:
                self.step_status.setSkipped(True)
            else:
                results = yield self._start_deferred
        finally:
            self._start_deferred = None
            unhandled = self._start_unhandled_deferreds
            self._start_unhandled_deferreds = None
            self.updateSummary()

        # Wait for any possibly-unhandled deferreds.  If any fail, change the
        # result to EXCEPTION and log.
        if unhandled:
            unhandled_results = yield defer.DeferredList(unhandled,
                                                         consumeErrors=True)
            for success, res in unhandled_results:
                if not success:
                    log.err(
                        res, "from an asynchronous method executed in an old-style step")
                    results = EXCEPTION

        defer.returnValue(results)

    def finished(self, results):
        assert self._start_deferred, \
            "finished() can only be called from old steps implementing start()"
        self._start_deferred.callback(results)

    def failed(self, why):
        assert self._start_deferred, \
            "failed() can only be called from old steps implementing start()"
        self._start_deferred.errback(why)

    def isNewStyle(self):
        # **temporary** method until new-style steps are the only supported style
        return self.run.im_func is not BuildStep.run.im_func

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

    def addLog(self, name, type='s', logEncoding=None):
        d = self.master.data.updates.newLog(self.stepid,
                                            util.ascii2unicode(name),
                                            unicode(type))

        @d.addCallback
        def newLog(logid):
            return self._newLog(name, type, logid, logEncoding)
        return d
    addLog_newStyle = addLog

    def addLog_oldStyle(self, name, type='s', logEncoding=None):
        # create a logfile instance that acts like old-style status logfiles
        # begin to create a new-style logfile
        loog_d = self.addLog_newStyle(name, type, logEncoding)
        self._start_unhandled_deferreds.append(loog_d)
        # and wrap the deferred that will eventually fire with that logfile
        # into a write-only logfile instance
        wrapper = SyncLogFileWrapper(self, name, loog_d)
        self._logFileWrappers[name] = wrapper
        return wrapper

    def getLog(self, name):
        return self.logs[name]

    def getLog_oldStyle(self, name):
        return self._logFileWrappers[name]

    @_maybeUnhandled
    @defer.inlineCallbacks
    def addCompleteLog(self, name, text):
        log.msg("addCompleteLog(%s)" % name)
        logid = yield self.master.data.updates.newLog(self.stepid,
                                                      util.ascii2unicode(name), u't')
        l = self._newLog(name, u't', logid)
        yield l.addContent(text)
        yield l.finish()

    @_maybeUnhandled
    @defer.inlineCallbacks
    def addHTMLLog(self, name, html):
        log.msg("addHTMLLog(%s)" % name)
        logid = yield self.master.data.updates.newLog(self.stepid,
                                                      util.ascii2unicode(name), u'h')
        l = self._newLog(name, u'h', logid)
        yield l.addContent(html)
        yield l.finish()

    @defer.inlineCallbacks
    def addLogWithFailure(self, why, logprefix=""):
        # helper for showing exceptions to the users
        try:
            yield self.addCompleteLog(logprefix + "err.text", why.getTraceback())
            yield self.addHTMLLog(logprefix + "err.html", formatFailure(why))
        except Exception:
            log.err(Failure(), "error while formatting exceptions")

    def addLogWithException(self, why, logprefix=""):
        return self.addLogWithFailure(Failure(why), logprefix)

    def addLogObserver(self, logname, observer):
        assert interfaces.ILogObserver.providedBy(observer)
        observer.setStep(self)
        self._pendingLogObservers.append((logname, observer))
        self._connectPendingLogObservers()

    def _newLog(self, name, type, logid, logEncoding=None):
        if not logEncoding:
            logEncoding = self.logEncoding
        if not logEncoding:
            logEncoding = self.master.config.logEncoding
        log = plog.Log.new(self.master, name, type, logid, logEncoding)
        self.logs[name] = log
        self._connectPendingLogObservers()
        return log

    def _connectPendingLogObservers(self):
        for logname, observer in self._pendingLogObservers[:]:
            if logname in self.logs:
                observer.setLog(self.logs[logname])
                self._pendingLogObservers.remove((logname, observer))

    @_maybeUnhandled
    @defer.inlineCallbacks
    def addURL(self, name, url):
        yield self.master.data.updates.addStepURL(self.stepid, unicode(name), unicode(url))
        self.step_status.addURL(name, url)
        defer.returnValue(None)

    @defer.inlineCallbacks
    def runCommand(self, command):
        self.cmd = command
        command.buildslave = self.buildslave
        try:
            res = yield command.run(self, self.remote, self.build.builder.name)
        finally:
            self.cmd = None
        defer.returnValue(res)

    def hasStatistic(self, name):
        return name in self.statistics

    def getStatistic(self, name, default=None):
        return self.statistics.get(name, default)

    def getStatistics(self):
        return self.statistics.copy()

    def setStatistic(self, name, value):
        self.statistics[name] = value


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

    def isNewStyle(self):
        # LoggingBuildStep subclasses are never new-style
        return False

    def addLogFile(self, logname, filename):
        self.logfiles[logname] = filename

    def buildCommandKwargs(self):
        kwargs = dict()
        kwargs['logfiles'] = self.logfiles
        return kwargs

    def startCommand(self, cmd, errorMessages=[]):
        log.msg("ShellCommand.startCommand(cmd=%s)" % (cmd,))
        log.msg("  cmd.args = %r" % (cmd.args))
        self.cmd = cmd  # so we can interrupt it
        self.step_status.setText(self.describe(False))

        # stdio is the first log
        self.stdio_log = stdio_log = self.addLog("stdio")
        cmd.useLog(stdio_log, closeWhenFinished=True)
        for em in errorMessages:
            stdio_log.addHeader(em)
            # TODO: consider setting up self.stdio_log earlier, and have the
            # code that passes in errorMessages instead call
            # self.stdio_log.addHeader() directly.

        # there might be other logs
        self.setupLogfiles(cmd, self.logfiles)

        d = self.runCommand(cmd)  # might raise ConnectionLost
        d.addCallback(lambda res: self.commandComplete(cmd))

        # TODO: when the status.LogFile object no longer exists, then this
        # method will a synthetic logfile for old-style steps, and to be called
        # without the `logs` parameter for new-style steps.  Unfortunately,
        # lots of createSummary methods exist, but don't look at the log, so
        # it's difficult to optimize when the synthetic logfile is needed.
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
        if self.step_status.isWaitingForLocks():
            self.addCompleteLog(
                'cancelled while waiting for locks', str(reason))
        else:
            self.addCompleteLog('cancelled', str(reason))

        if self.cmd:
            d = self.cmd.interrupt(reason)
            d.addErrback(log.err, 'while cancelling command')

    def checkDisconnect(self, f):
        # this is now handled by self.failed
        log.msg("WARNING: step %s uses deprecated checkDisconnect method")
        return f

    def commandComplete(self, cmd):
        pass

    def createSummary(self, stdio):
        pass

    def evaluateCommand(self, cmd):
        # NOTE: log_eval_func is undocumented, and will die with LoggingBuildStep/ShellCOmmand
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
        elif results == CANCELLED:
            return self.describe(True) + ["cancelled"]
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
        return defer.succeed(None)


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
        assert self.isNewStyle(
        ), "ShellMixin is only compatible with new-style steps"
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
        if not self.workdir:
            if callable(self.build.workdir):
                kwargs['workdir'] = self.build.workdir(self.build.sources)
            else:
                kwargs['workdir'] = self.build.workdir

        # the rest of the args go to RemoteShellCommand
        cmd = remotecommand.RemoteShellCommand(**kwargs)

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
# NOTE: log_eval_func is undocumented, and will die with LoggingBuildStep/ShellCOmmand


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
