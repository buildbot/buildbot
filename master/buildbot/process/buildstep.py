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
from future.utils import PY3
from future.utils import iteritems
from future.utils import itervalues
from future.utils import raise_with_traceback
from future.utils import string_types
from future.utils import text_type

import re

from twisted.internet import defer
from twisted.internet import error
from twisted.python import util as twutil
from twisted.python import components
from twisted.python import deprecate
from twisted.python import failure
from twisted.python import log
from twisted.python import versions
from twisted.python.compat import NativeStringIO
from twisted.python.failure import Failure
from twisted.python.reflect import accumulateClassList
from twisted.web.util import formatFailure
from zope.interface import implementer

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot.interfaces import WorkerTooOldError
from buildbot.process import log as plog
from buildbot.process import logobserver
from buildbot.process import properties
from buildbot.process import remotecommand
from buildbot.process import results
# (WithProperties used to be available in this module)
from buildbot.process.properties import WithProperties
from buildbot.process.results import ALL_RESULTS
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.process.results import worst_status
from buildbot.util import bytes2NativeString
from buildbot.util import debounce
from buildbot.util import flatten
from buildbot.worker_transition import WorkerAPICompatMixin
from buildbot.worker_transition import deprecatedWorkerClassMethod


class BuildStepFailed(Exception):
    pass


class BuildStepCancelled(Exception):
    # used internally for signalling
    pass


class CallableAttributeError(Exception):
    # attribute error raised from a callable run inside a property
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


@implementer(interfaces.IBuildStepFactory)
class _BuildStepFactory(util.ComparableMixin):

    """
    This is a wrapper to record the arguments passed to as BuildStep subclass.
    We use an instance of this class, rather than a closure mostly to make it
    easier to test that the right factories are getting created.
    """
    compare_attrs = ('factory', 'args', 'kwargs')

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
    wrap.__wrapped__ = fn
    twutil.mergeFunctionMetadata(fn, wrap)
    return wrap


class SyncLogFileWrapper(logobserver.LogObserver):

    # A temporary wrapper around process.log.Log to emulate *synchronous*
    # writes to the logfile by handling the Deferred from each add* operation
    # as part of the step's _start_unhandled_deferreds.  This has to handle
    # the tricky case of adding data to a log *before* addLog has returned!
    # this also adds the read-only methods such as getText

    # old constants from the status API
    HEADER = 0
    STDERR = 1
    STDOUT = 2

    def __init__(self, step, name, addLogDeferred):
        self.step = step
        self.name = name
        self.delayedOperations = []
        self.asyncLogfile = None
        self.chunks = []
        self.finished = False
        self.finishDeferreds = []

        self.step._sync_addlog_deferreds.append(addLogDeferred)

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
        data = bytes2NativeString(data)
        self.chunks.append((self.STDOUT, data))
        self._delay(lambda: self.asyncLogfile.addStdout(data))

    def addStderr(self, data):
        data = bytes2NativeString(data)
        self.chunks.append((self.STDERR, data))
        self._delay(lambda: self.asyncLogfile.addStderr(data))

    def addHeader(self, data):
        data = bytes2NativeString(data)
        self.chunks.append((self.HEADER, data))
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
        return "".join(self.getChunks([self.STDOUT, self.STDERR], onlyText=True))

    def readlines(self):
        alltext = "".join(self.getChunks([self.STDOUT], onlyText=True))
        io = NativeStringIO(alltext)
        return io.readlines()

    def getChunks(self, channels=None, onlyText=False):
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
        self.finishDeferreds.append(d)
        self._maybeFinished()


class BuildStepStatus(object):
    # used only for old-style steps
    pass


@implementer(interfaces.IBuildStep)
class BuildStep(results.ResultComputingConfigMixin,
                properties.PropertiesMixin,
                WorkerAPICompatMixin,
                util.ComparableMixin):

    alwaysRun = False
    doStepIf = True
    hideStepIf = False
    compare_attrs = ("_factory",)
    # properties set on a build step are, by nature, always runtime properties
    set_runtime_properties = True

    renderables = results.ResultComputingConfigMixin.resultConfig + [
        'alwaysRun',
        'description',
        'descriptionDone',
        'descriptionSuffix',
        'doStepIf',
        'hideStepIf',
        'workdir',
    ]

    # 'parms' holds a list of all the parameters we care about, to allow
    # users to instantiate a subclass of BuildStep with a mixture of
    # arguments, some of which are for us, some of which are for the subclass
    # (or a delegate of the subclass, like how ShellCommand delivers many
    # arguments to the RemoteShellCommand that it creates). Such delegating
    # subclasses will use this list to figure out which arguments are meant
    # for us and which should be given to someone else.
    parms = [
        'alwaysRun',
        'description',
        'descriptionDone',
        'descriptionSuffix',
        'doStepIf',
        'flunkOnFailure',
        'flunkOnWarnings',
        'haltOnFailure',
        'updateBuildSummaryPolicy',
        'hideStepIf',
        'locks',
        'logEncoding',
        'name',
        'progressMetrics',
        'useProgress',
        'warnOnFailure',
        'warnOnWarnings',
        'workdir',
    ]

    name = "generic"
    description = None  # set this to a list of short strings to override
    descriptionDone = None  # alternate description when the step is complete
    descriptionSuffix = None  # extra information to append to suffix
    updateBuildSummaryPolicy = None
    locks = []
    progressMetrics = ()  # 'time' is implicit
    useProgress = True  # set to False if step is really unpredictable
    build = None
    step_status = None
    progress = None
    logEncoding = None
    cmd = None
    rendered = False  # true if attributes are rendered
    _workdir = None
    _waitingForLocks = False

    def _run_finished_hook(self):
        return None  # override in tests

    def __init__(self, **kwargs):
        self.worker = None
        self._registerOldWorkerAttr("worker", name="buildslave")

        for p in self.__class__.parms:
            if p in kwargs:
                setattr(self, p, kwargs.pop(p))

        if kwargs:
            config.error("%s.__init__ got unexpected keyword argument(s) %s"
                         % (self.__class__, list(kwargs)))
        self._pendingLogObservers = []

        if not isinstance(self.name, str):
            config.error("BuildStep name must be a string: %r" % (self.name,))

        if isinstance(self.description, str):
            self.description = [self.description]
        if isinstance(self.descriptionDone, str):
            self.descriptionDone = [self.descriptionDone]
        if isinstance(self.descriptionSuffix, str):
            self.descriptionSuffix = [self.descriptionSuffix]

        if self.updateBuildSummaryPolicy is None:  # compute default value for updateBuildSummaryPolicy
            self.updateBuildSummaryPolicy = [EXCEPTION, RETRY, CANCELLED]
            if self.flunkOnFailure or self.haltOnFailure or self.warnOnFailure:
                self.updateBuildSummaryPolicy.append(FAILURE)
            if self.warnOnWarnings or self.flunkOnWarnings:
                self.updateBuildSummaryPolicy.append(WARNINGS)
            self.updateBuildSummaryPolicy
        if self.updateBuildSummaryPolicy is False:
            self.updateBuildSummaryPolicy = []
        if self.updateBuildSummaryPolicy is True:
            self.updateBuildSummaryPolicy = ALL_RESULTS
        if not isinstance(self.updateBuildSummaryPolicy, list):
            config.error("BuildStep updateBuildSummaryPolicy must be "
                         "a list of result ids or boolean but it is %r" %
                         (self.updateBuildSummaryPolicy,))
        self._acquiringLock = None
        self.stopped = False
        self.master = None
        self.statistics = {}
        self.logs = {}
        self._running = False
        self.stepid = None
        self.results = None
        self._start_unhandled_deferreds = None

    def __new__(klass, *args, **kwargs):
        self = object.__new__(klass)
        self._factory = _BuildStepFactory(klass, *args, **kwargs)
        return self

    def __str__(self):
        args = [repr(x) for x in self._factory.args]
        args.extend([str(k) + "=" + repr(v) for k, v in self._factory.kwargs.items()])
        return "{}({})".format(
            self.__class__.__name__, ", ".join(args))
    __repr__ = __str__

    def setBuild(self, build):
        self.build = build
        self.master = self.build.master

    def setWorker(self, worker):
        self.worker = worker
    deprecatedWorkerClassMethod(
        locals(), setWorker, compat_name="setBuildSlave")

    @deprecate.deprecated(versions.Version("buildbot", 0, 9, 0))
    def setDefaultWorkdir(self, workdir):
        if self._workdir is None:
            self._workdir = workdir

    @property
    def workdir(self):
        # default the workdir appropriately
        if self._workdir is not None or self.build is None:
            return self._workdir
        else:
            # see :ref:`Factory-Workdir-Functions` for details on how to
            # customize this
            if callable(self.build.workdir):
                try:
                    return self.build.workdir(self.build.sources)
                except AttributeError as e:
                    # if the callable raises an AttributeError
                    # python thinks it is actually workdir that is not existing.
                    # python will then swallow the attribute error and call
                    # __getattr__ from worker_transition
                    raise raise_with_traceback(CallableAttributeError(e))
                    # we re-raise the original exception by changing its type,
                    # but keeping its stacktrace
            else:
                return self.build.workdir

    @workdir.setter
    def workdir(self, workdir):
        self._workdir = workdir

    def addFactoryArguments(self, **kwargs):
        # this is here for backwards compatibility
        pass

    def _getStepFactory(self):
        return self._factory

    def setupProgress(self):
        # this function temporarily does nothing
        pass

    def setProgress(self, metric, value):
        # this function temporarily does nothing
        pass

    def getCurrentSummary(self):
        if self.description is not None:
            stepsumm = util.join_list(self.description)
            if self.descriptionSuffix:
                stepsumm += u' ' + util.join_list(self.descriptionSuffix)
        else:
            stepsumm = u'running'
        return {u'step': stepsumm}

    def getResultSummary(self):
        if self.descriptionDone is not None or self.description is not None:
            stepsumm = util.join_list(self.descriptionDone or self.description)
            if self.descriptionSuffix:
                stepsumm += u' ' + util.join_list(self.descriptionSuffix)
        else:
            stepsumm = u'finished'

        if self.results != SUCCESS:
            stepsumm += u' (%s)' % Results[self.results]

        return {u'step': stepsumm}

    @defer.inlineCallbacks
    def getBuildResultSummary(self):
        summary = yield self.getResultSummary()
        if self.results in self.updateBuildSummaryPolicy and u'build' not in summary and u'step' in summary:
            summary[u'build'] = summary[u'step']
        defer.returnValue(summary)

    @debounce.method(wait=1)
    @defer.inlineCallbacks
    def updateSummary(self):
        def methodInfo(m):
            import inspect
            lines = inspect.getsourcelines(m)
            return "\nat %s:%s:\n %s" % (
                inspect.getsourcefile(m), lines[1], "\n".join(lines[0]))
        if not self._running:
            summary = yield self.getResultSummary()
            if not isinstance(summary, dict):
                raise TypeError('getResultSummary must return a dictionary: ' +
                                methodInfo(self.getResultSummary))
        else:
            summary = yield self.getCurrentSummary()
            if not isinstance(summary, dict):
                raise TypeError('getCurrentSummary must return a dictionary: ' +
                                methodInfo(self.getCurrentSummary))

        stepResult = summary.get('step', u'finished')
        if not isinstance(stepResult, text_type):
            raise TypeError("step result string must be unicode (got %r)"
                            % (stepResult,))
        if self.stepid is not None:
            stepResult = self.build.properties.cleanupTextFromSecrets(stepResult)
            yield self.master.data.updates.setStepStateString(self.stepid,
                                                              stepResult)

        if not self._running:
            buildResult = summary.get('build', None)
            if buildResult and not isinstance(buildResult, text_type):
                raise TypeError("build result string must be unicode")
    # updateSummary gets patched out for old-style steps, so keep a copy we can
    # call internally for such steps
    realUpdateSummary = updateSummary

    @defer.inlineCallbacks
    def addStep(self):
        # create and start the step, noting that the name may be altered to
        # ensure uniqueness
        self.name = yield self.build.render(self.name)
        self.stepid, self.number, self.name = yield self.master.data.updates.addStep(
            buildid=self.build.buildid,
            name=util.ascii2unicode(self.name))
        yield self.master.data.updates.startStep(self.stepid)

    @defer.inlineCallbacks
    def startStep(self, remote):
        self.remote = remote

        yield self.addStep()
        self.locks = yield self.build.render(self.locks)

        # convert all locks into their real form
        self.locks = [(self.build.builder.botmaster.getLockFromLockAccess(access), access)
                      for access in self.locks]
        # then narrow WorkerLocks down to the worker that this build is being
        # run on
        self.locks = [(l.getLock(self.build.workerforbuilder.worker), la)
                      for l, la in self.locks]

        for l, la in self.locks:
            if l in self.build.locks:
                log.msg("Hey, lock %s is claimed by both a Step (%s) and the"
                        " parent Build (%s)" % (l, self, self.build))
                raise RuntimeError("lock claimed by both Step and Build")

        try:
            # set up locks
            yield self.acquireLocks()

            if self.stopped:
                raise BuildStepCancelled

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
            self.realUpdateSummary()

            # check doStepIf (after rendering)
            if isinstance(self.doStepIf, bool):
                doStep = self.doStepIf
            else:
                doStep = yield self.doStepIf(self)

            # run -- or skip -- the step
            if doStep:
                try:
                    self._running = True
                    self.results = yield self.run()
                finally:
                    self._running = False
            else:
                self.results = SKIPPED

        # NOTE: all of these `except` blocks must set self.results immediately!
        except BuildStepCancelled:
            self.results = CANCELLED

        except BuildStepFailed:
            self.results = FAILURE

        except error.ConnectionLost:
            self.results = RETRY

        except Exception:
            self.results = EXCEPTION
            why = Failure()
            log.err(why, "BuildStep.failed; traceback follows")
            yield self.addLogWithFailure(why)

        if self.stopped and self.results != RETRY:
            # We handle this specially because we don't care about
            # the return code of an interrupted command; we know
            # that this should just be exception due to interrupt
            # At the same time we must respect RETRY status because it's used
            # to retry interrupted build due to some other issues for example
            # due to worker lost
            if self.results != CANCELLED:
                self.results = EXCEPTION

        # update the summary one last time, make sure that completes,
        # and then don't update it any more.
        self.realUpdateSummary()
        yield self.realUpdateSummary.stop()

        # determine whether we should hide this step
        hidden = self.hideStepIf
        if callable(hidden):
            try:
                hidden = hidden(self.results, self)
            except Exception:
                why = Failure()
                log.err(why, "hidden callback failed; traceback follows")
                yield self.addLogWithFailure(why)
                self.results = EXCEPTION
                hidden = False

        yield self.master.data.updates.finishStep(self.stepid, self.results,
                                                  hidden)
        # finish unfinished logs
        all_finished = yield self.finishUnfinishedLogs()
        if not all_finished:
            self.results = EXCEPTION
        self.releaseLocks()

        defer.returnValue(self.results)

    @defer.inlineCallbacks
    def finishUnfinishedLogs(self):
        ok = True
        not_finished_logs = [v for (k, v) in iteritems(self.logs)
                             if not v.finished]
        finish_logs = yield defer.DeferredList([v.finish() for v in not_finished_logs],
                                               consumeErrors=True)
        for success, res in finish_logs:
            if not success:
                log.err(res, "when trying to finish a log")
                ok = False
        defer.returnValue(ok)

    def acquireLocks(self, res=None):
        self._acquiringLock = None
        if not self.locks:
            return defer.succeed(None)
        if self.stopped:
            return defer.succeed(None)
        log.msg("acquireLocks(step %s, locks %s)" % (self, self.locks))
        for lock, access in self.locks:
            if not lock.isAvailable(self, access):
                self._waitingForLocks = True
                log.msg("step %s waiting for lock %s" % (self, lock))
                d = lock.waitUntilMaybeAvailable(self, access)
                d.addCallback(self.acquireLocks)
                self._acquiringLock = (lock, access, d)
                return d
        # all locks are available, claim them all
        for lock, access in self.locks:
            lock.claim(self, access)
        self._waitingForLocks = False
        return defer.succeed(None)

    @defer.inlineCallbacks
    def run(self):
        self._start_deferred = defer.Deferred()
        unhandled = self._start_unhandled_deferreds = []
        self._sync_addlog_deferreds = []
        try:
            # here's where we set things up for backward compatibility for
            # old-style steps, using monkey patches so that new-style steps
            # aren't bothered by any of this equipment

            # monkey-patch self.step_status.{setText,setText2} back into
            # existence for old steps, signalling an update to the summary
            self.step_status = BuildStepStatus()
            self.step_status.setText = lambda text: self.realUpdateSummary()
            self.step_status.setText2 = lambda text: self.realUpdateSummary()

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

            # old-style steps shouldn't be calling updateSummary
            def updateSummary():
                assert 0, 'updateSummary is only valid on new-style steps'
            self.updateSummary = updateSummary

            results = yield self.start()
            if results is not None:
                self._start_deferred.callback(results)
            results = yield self._start_deferred
        finally:
            # hook for tests
            # assert so that it is only run in non optimized mode
            assert self._run_finished_hook() is None
            # wait until all the sync logs have been actually created before
            # finishing
            yield defer.DeferredList(self._sync_addlog_deferreds,
                                     consumeErrors=True)
            self._start_deferred = None
            unhandled = self._start_unhandled_deferreds
            self.realUpdateSummary()

            # Wait for any possibly-unhandled deferreds.  If any fail, change the
            # result to EXCEPTION and log.
            while unhandled:
                self._start_unhandled_deferreds = []
                unhandled_results = yield defer.DeferredList(unhandled,
                                                             consumeErrors=True)
                for success, res in unhandled_results:
                    if not success:
                        log.err(
                            res, "from an asynchronous method executed in an old-style step")
                        results = EXCEPTION
                unhandled = self._start_unhandled_deferreds

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
        if PY3:
            return self.run.__func__ is not BuildStep.run
        return self.run.im_func is not BuildStep.run.im_func

    def start(self):
        # New-style classes implement 'run'.
        # Old-style classes implemented 'start'. Advise them to do 'run'
        # instead.
        raise NotImplementedError("your subclass must implement run()")

    def interrupt(self, reason):
        # TODO: consider adding an INTERRUPTED or STOPPED status to use
        # instead of FAILURE, might make the text a bit more clear.
        # 'reason' can be a Failure, or text
        self.stopped = True
        if self._acquiringLock:
            lock, access, d = self._acquiringLock
            lock.stopWaitingUntilAvailable(self, access, d)
            d.callback(None)

        if self._waitingForLocks:
            self.addCompleteLog(
                'cancelled while waiting for locks', str(reason))
        else:
            self.addCompleteLog('cancelled', str(reason))

        if self.cmd:
            d = self.cmd.interrupt(reason)
            d.addErrback(log.err, 'while cancelling command')

    def releaseLocks(self):
        log.msg("releaseLocks(%s): %s" % (self, self.locks))
        for lock, access in self.locks:
            if lock.isOwner(self, access):
                lock.release(self, access)
            else:
                # This should only happen if we've been interrupted
                assert self.stopped

    # utility methods that BuildSteps may find useful

    def workerVersion(self, command, oldversion=None):
        return self.build.getWorkerCommandVersion(command, oldversion)
    deprecatedWorkerClassMethod(locals(), workerVersion)

    def workerVersionIsOlderThan(self, command, minversion):
        sv = self.build.getWorkerCommandVersion(command, None)
        if sv is None:
            return True
        if [int(s) for s in sv.split(".")] < [int(m) for m in minversion.split(".")]:
            return True
        return False
    deprecatedWorkerClassMethod(locals(), workerVersionIsOlderThan)

    def checkWorkerHasCommand(self, command):
        if not self.workerVersion(command):
            message = "worker is too old, does not know about %s" % command
            raise WorkerTooOldError(message)
    deprecatedWorkerClassMethod(locals(), checkWorkerHasCommand)

    def getWorkerName(self):
        return self.build.getWorkerName()
    deprecatedWorkerClassMethod(locals(), getWorkerName)

    def addLog(self, name, type='s', logEncoding=None):
        d = self.master.data.updates.addLog(self.stepid,
                                            util.ascii2unicode(name),
                                            text_type(type))

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
        logid = yield self.master.data.updates.addLog(self.stepid,
                                                      util.ascii2unicode(name), u't')
        _log = self._newLog(name, u't', logid)
        yield _log.addContent(text)
        yield _log.finish()

    @_maybeUnhandled
    @defer.inlineCallbacks
    def addHTMLLog(self, name, html):
        logid = yield self.master.data.updates.addLog(self.stepid,
                                                      util.ascii2unicode(name), u'h')
        _log = self._newLog(name, u'h', logid)
        html = bytes2NativeString(html)
        yield _log.addContent(html)
        yield _log.finish()

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
        yield self.master.data.updates.addStepURL(self.stepid, text_type(name), text_type(url))
        defer.returnValue(None)

    @defer.inlineCallbacks
    def runCommand(self, command):
        self.cmd = command
        command.worker = self.worker
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

    def _describe(self, done=False):
        # old-style steps expect this function to exist
        assert not self.isNewStyle()
        return []

    def describe(self, done=False):
        # old-style steps expect this function to exist
        assert not self.isNewStyle()
        desc = self._describe(done)
        if not desc:
            return []
        if self.descriptionSuffix:
            desc += self.descriptionSuffix
        return desc


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

    def __init__(self, logfiles=None, lazylogfiles=False, log_eval_func=None,
                 *args, **kwargs):
        BuildStep.__init__(self, *args, **kwargs)

        if logfiles is None:
            logfiles = {}
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

    def startCommand(self, cmd, errorMessages=None):
        if errorMessages is None:
            errorMessages = []
        log.msg("ShellCommand.startCommand(cmd=%s)" % (cmd,))
        log.msg("  cmd.args = %r" % (cmd.args))
        self.cmd = cmd  # so we can interrupt it

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

        @d.addCallback
        def _gotResults(results):
            self.setStatus(cmd, results)
            return results
        d.addCallback(self.finished)
        d.addErrback(self.failed)

    def setupLogfiles(self, cmd, logfiles):
        for logname, remotefilename in iteritems(logfiles):
            if self.lazylogfiles:
                # Ask RemoteCommand to watch a logfile, but only add
                # it when/if we see any data.
                #
                # The dummy default argument local_logname is a work-around for
                # Python name binding; default values are bound by value, but
                # captured variables in the body are bound by name.
                def callback(cmd_arg, local_logname=logname):
                    return self.addLog(local_logname)
                cmd.useLogDelayed(logname, callback, True)
            else:
                # add a LogFile
                newlog = self.addLog(logname)
                # and tell the RemoteCommand to feed it
                cmd.useLog(newlog, True)

    def checkDisconnect(self, f):
        # this is now handled by self.failed
        log.msg("WARNING: step %s uses deprecated checkDisconnect method")
        return f

    def commandComplete(self, cmd):
        pass

    def createSummary(self, stdio):
        pass

    def evaluateCommand(self, cmd):
        # NOTE: log_eval_func is undocumented, and will die with
        # LoggingBuildStep/ShellCOmmand
        if self.log_eval_func:
            # self.step_status probably doesn't have the desired behaviors, but
            # those were never well-defined..
            return self.log_eval_func(cmd, self.step_status)
        return cmd.results()

    # TODO: delete
    def getText(self, cmd, results):
        if results == SUCCESS:
            return self.describe(True)
        elif results == WARNINGS:
            return self.describe(True) + ["warnings"]
        elif results == EXCEPTION:
            return self.describe(True) + ["exception"]
        elif results == CANCELLED:
            return self.describe(True) + ["cancelled"]
        return self.describe(True) + ["failed"]

    # TODO: delete
    def getText2(self, cmd, results):
        return [self.name]

    # TODO: delete
    def maybeGetText2(self, cmd, results):
        if results == SUCCESS:
            # successful steps do not add anything to the build's text
            pass
        elif results == WARNINGS:
            if (self.flunkOnWarnings or self.warnOnWarnings):
                # we're affecting the overall build, so tell them why
                return self.getText2(cmd, results)
        else:
            if (self.haltOnFailure or self.flunkOnFailure or
                    self.warnOnFailure):
                # we're affecting the overall build, so tell them why
                return self.getText2(cmd, results)
        return []

    def setStatus(self, cmd, results):
        self.realUpdateSummary()
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

    def runGlob(self, path):
        return self._runRemoteCommand(
            'glob', True, {'path': path, 'logEnviron': False},
            makeResult=lambda cmd: cmd.updates['files'][0])


class ShellMixin(object):

    command = None
    env = {}
    want_stdout = True
    want_stderr = True
    usePTY = None
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

    def setupShellMixin(self, constructorArgs, prohibitArgs=None):
        assert self.isNewStyle(
        ), "ShellMixin is only compatible with new-style steps"
        constructorArgs = constructorArgs.copy()

        if prohibitArgs is None:
            prohibitArgs = []

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
        for arg in list(constructorArgs):
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

        # store command away for display
        self.command = kwargs['command']

        # check for the usePTY flag
        if kwargs['usePTY'] is not None:
            if self.workerVersionIsOlderThan("shell", "2.7"):
                if stdio is not None:
                    yield stdio.addHeader(
                        "NOTE: worker does not allow master to override usePTY\n")
                del kwargs['usePTY']

        # check for the interruptSignal flag
        if kwargs["interruptSignal"] and self.workerVersionIsOlderThan("shell", "2.15"):
            if stdio is not None:
                yield stdio.addHeader(
                    "NOTE: worker does not allow master to specify interruptSignal\n")
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
        for logname, remotefilename in iteritems(self.logfiles):
            if self.lazylogfiles:
                # it's OK if this does, or does not, return a Deferred
                def callback(cmd_arg, local_logname=logname):
                    return self.addLog(local_logname)
                cmd.useLogDelayed(logname, callback, True)
            else:
                # add a LogFile
                newlog = yield self.addLog(logname)
                # and tell the RemoteCommand to feed it
                cmd.useLog(newlog, False)

        defer.returnValue(cmd)

    def getResultSummary(self):
        summary = util.command_to_string(self.command)
        if not summary:
            return super(ShellMixin, self).getResultSummary()
        return {u'step': summary}

# Parses the logs for a list of regexs. Meant to be invoked like:
# regexes = ((re.compile(...), FAILURE), (re.compile(...), WARNINGS))
# self.addStep(ShellCommand,
#   command=...,
#   ...,
#   log_eval_func=lambda c,s: regex_log_evaluator(c, s, regexs)
# )
# NOTE: log_eval_func is undocumented, and will die with
# LoggingBuildStep/ShellCOmmand


def regex_log_evaluator(cmd, _, regexes):
    worst = cmd.results()
    for err, possible_status in regexes:
        # worst_status returns the worse of the two status' passed to it.
        # we won't be changing "worst" unless possible_status is worse than it,
        # so we don't even need to check the log if that's the case
        if worst_status(worst, possible_status) == possible_status:
            if isinstance(err, string_types):
                err = re.compile(".*%s.*" % err, re.DOTALL)
            for l in itervalues(cmd.logs):
                if err.search(l.getText()):
                    worst = possible_status
    return worst


_hush_pyflakes = [WithProperties]
del _hush_pyflakes
