.. _New-Style-Build-Steps:

New-Style Build Steps
=====================

In Buildbot-0.9.0, many operations performed by BuildStep subclasses return a Deferred.
As a result, custom build steps which call these methods will need to be rewritten.

Buildbot-0.8.9 supports old-style steps natively, while new-style steps are emulated.
Buildbot-0.9.0 supports new-style steps natively, while old-style steps are emulated.
Later versions of Buildbot will not support old-style steps at all.
All custom steps should be rewritten in the new style as soon as possible.

Buildbot distinguishes new-style from old-style steps by the presence of a :py:meth:`~buildbot.process.buildstep.BuildStep.run` method.
If this method is present, then the step is a new-style step.

Summary of Changes
++++++++++++++++++

* New-style steps have a ``run`` method that is simpler to implement than the old ``start`` method.
* Many methods are now asynchronous (return Deferreds), as they perform operations on the database.
* Logs are now implemented by a completely different class.
  This class supports the same log-writing methods (``addStderr`` and so on), although they are now asynchronous.
  However, it does not support log-reading methods such as ``getText``.
  It was never advisable to handle logs as enormous strings.
  New-style steps should, instead, use a LogObserver or (in Buildbot-0.9.0) fetch log lines bit by bit using the data API.
* :py:class:`buildbot.process.buildstep.LoggingBuildStep` is deprecated and cannot be used in new-style steps.
  Mix in :py:class:`buildbot.process.buildstep.ShellMixin` instead.
* Step strings, derived by parameters like ``description``, ``descriptionDone``, and ``descriptionSuffix``, are no longer treated as lists.
  For backward compatibility, the parameters may still be given as lists, but will be joined with spaces during execution (using :py:func:`~buildbot.util.join_list`).

Backward Compatibility
++++++++++++++++++++++

Some hacks are in place to support old-style steps.
These hacks are only activated when an old-style step is detected.
Support for old-style steps will be dropped soon after Buildbot-0.9.0 is released.

* The Deferreds from all asynchronous methods invoked during step execution are gathered internally.
  The step is not considered finished until all such Deferreds have fired, and is marked EXCEPTION if any fail.
  For logfiles, this is accomplished by means of a synchronous wrapper class.

* Logfile data is available while the step is still in memory.
  This means that logs returned from ``step.getLog`` have the expected methods ``getText``, ``readlines`` and so on.

* :py:class:`~buildbot.steps.shell.ShellCommand` subclasses implicitly gather all stdio output in memory and provide it to the ``createSummary`` method.

Rewriting ``start``
+++++++++++++++++++

If your custom buildstep implements the ``start`` method, then rename that method to ``run`` and set it up to return a Deferred, either explicitly or via ``inlineCallbacks``.
The value of the Deferred should be the result of the step (one of the codes in :py:mod:`buildbot.process.results`), or a Twisted failure instance to complete the step as EXCEPTION.
The new ``run`` method should *not* call ``self.finished`` or ``self.failed``, instead signalling the same via Deferred.

For example, the following old-style ``start`` method ::


    def start(self):  ## old style
        cmd = remotecommand.RemoteCommand('stat', {'file': self.file })
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.convertResult(cmd))
        d.addErrback(self.failed)

Becomes ::

    @defer.inlineCallbacks
    def run(self):  ## new style
        cmd = remotecommand.RemoteCommand('stat', {'file': self.file })
        yield self.runCommand(cmd)
        defer.returnValue(self.convertResult(cmd))

Newly Asynchronous Methods
++++++++++++++++++++++++++

The following methods now return a Deferred:

* :py:meth:`buildbot.process.buildstep.BuildStep.addLog`
* ``log.addStdout``
* ``log.addStderr``
* ``log.addHeader``
* ``log.finish`` (see "Log Objects", below)
* :py:meth:`buildbot.process.remotecommand.RemoteCommand.addStdout`
* :py:meth:`buildbot.process.remotecommand.RemoteCommand.addStderr`
* :py:meth:`buildbot.process.remotecommand.RemoteCommand.addHeader`
* :py:meth:`buildbot.process.remotecommand.RemoteCommand.addToLog`
* :py:meth:`buildbot.process.buildstep.BuildStep.addCompleteLog`
* :py:meth:`buildbot.process.buildstep.BuildStep.addHTMLLog`
* :py:meth:`buildbot.process.buildstep.BuildStep.addURL`

Any custom code in a new-style step that calls these methods must handle the resulting Deferred.
In some cases, that means that the calling method's signature will change.
For example ::

    def summarize(self):  ## old-style
        for m in self.MESSAGES:
            if counts[m]:
                self.addCompleteLog(m, "".join(summaries[m]))
            self.setProperty("count-%s" % m, counts[m], "counter")

Is a synchronous function, not returning a Deferred.
However, when converted to a new-style test, it must handle Deferreds from the methods it calls, so it must be asynchronous.
Syntactically, ``inlineCallbacks`` makes the change fairly simple::

    @defer.inlineCallbacks
    def summarize(self):  ## new-style
        for m in self.MESSAGES:
            if counts[m]:
                yield self.addCompleteLog(m, "".join(summaries[m]))
            self.setProperty("count-%s" % m, counts[m], "counter")

However, this method's callers must now handle the Deferred that it returns.
All methods that can be overridden in custom steps can return a Deferred.

Properties
++++++++++

Good news!
The API for properties is the same synchronous API as was available in old-style steps.
Properties are handled synchronously during the build, and persisted to the database at completion of each step.

Log Objects
+++++++++++

Old steps had two ways of interacting with logfiles, both of which have changed.

The first is writing to logs while a step is executing.
When using :py:meth:`~buildbot.process.buildstep.BuildStep.addCompleteLog` or :py:meth:`~buildbot.process.buildstep.BuildStep.addHTMLLog`, this is straightforward, except that in new-style steps these methods return a Deferred.

The second method is via :py:meth:`buildbot.process.buildstep.BuildStep.addLog`.
In new-style steps, the returned object (via Deferred) has the following methods to add log content:

* :py:meth:`~buildbot.process.log.StreamLog.addStdout`
* :py:meth:`~buildbot.process.log.StreamLog.addStderr`
* :py:meth:`~buildbot.process.log.StreamLog.addHeader`
* :py:meth:`~buildbot.process.log.Log.finish`

All of these methods now return Deferreds.
None of the old log-reading methods are available on this object:

* ``hasContents``
* ``getText``
* ``readLines``
* ``getTextWithHeaders``
* ``getChunks``

If your step uses such methods, consider using a :class:`~buildbot.process.logobserver.LogObserver` instead, or using the Data API to get the required data.

The undocumented and unused ``subscribeConsumer`` method of logfiles has also been removed.

The :py:meth:`~buildbot.process.log.Log.subscribe` method now takes a callable, rather than an instance, and does not support catchup.
This method was primarily used by :py:class:`~buildbot.process.logobserver.LogObserver`, the implementation of which has been modified accordingly.
Any other uses of the subscribe method should be refactored to use a :py:class:`~buildbot.process.logobserver.LogObserver`.

Status Strings
++++++++++++++

The ``self.step_status.setText`` and ``setText2`` methods have been removed.
Similarly, the ``_describe`` and ``describe`` methods are not used in new-style steps.
In fact, steps no longer set their status directly.

Instead, steps call :py:meth:`buildbot.process.buildstep.BuildStep.updateSummary` whenever the status may have changed.
This method calls :py:meth:`~buildbot.process.buildstep.BuildStep.getCurrentSummary` or :py:meth:`~buildbot.process.buildstep.BuildStep.getResultSummary` as appropriate and update displays of the step's status.
Steps override the latter two methods to provide appropriate summaries.

Statistics
++++++++++

Support for statistics has been moved to the ``BuildStep`` and ``Build`` objects.
Calls to ``self.step_status.setStatistic`` should be rewritten as ``self.setStatistic``.
