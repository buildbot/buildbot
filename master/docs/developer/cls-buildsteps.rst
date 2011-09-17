BuildSteps
==========

.. py:module:: buildbot.process.buildstep

There are a few parent classes that are used as base classes for real
buildsteps.  This section describes the base classes.  The "leaf" classes are
described in :doc:`../manual/cfg-buildsteps`.

BuildStep
---------

.. py:class:: BuildStep(name, locks, haltOnFailure, flunkOnWarnings, flunkOnFailure, warnOnWarnings, warnOnFailure, alwaysRun, progressMetrics, useProgress, doStepIf)

    All constructor arguments must be given as keyword arguments.  Each
    constructor parameter is copied to the corresponding attribute.

    .. py:attribute:: name

        The name of the step.

    .. py:attribute:: locks

        List of locks for this step; see :ref:`Interlocks`.

    .. py:attribute:: progressMetrics

        List of names of metrics that should be used to track the progress of
        this build, and build ETA's for users.  This is generally set in the 

    .. py:attribute:: useProgress

        If true (the default), then ETAs will be calculated for this step using
        progress metrics.  If the step is known to have unpredictable timing
        (e.g., an incremental build), then this should be set to false.

    .. py:attribute:: doStepIf

        A callable to determine whether this step should be executed.  See
        :ref:`Buildstep-Common-Parameters` for details.

    The following attributes affect the behavior of the containing build:

    .. py:attribute:: haltOnFailure

        If true, the build will halt on a failure of this step, and not execute
        subsequent tests (except those with ``alwaysRun``).

    .. py:attribute:: flunkOnWarnings

        If true, the build will be marked as a failure if this step ends with
        warnings.

    .. py:attribute:: flunkOnFailure

        If true, the build will be marked as a failure if this step fails.

    .. py:attribute:: warnOnWarnings

        If true, the build will be marked as warnings, or worse, if this step
        ends with warnings.

    .. py:attribute:: warnOnFailure

        If true, the build will be marked as warnings, or worse, if this step
        fails.

    .. py:attribute:: alwaysRun

        If true, the step will run even if a previous step halts the build with
        ``haltOnFailure``.

    A step acts as a factory for more steps.  See
    :ref:`Writing-BuildStep-Constructors` for advice on writing subclass
    constructors.  The following methods handle this factory behavior.

    .. py:method:: addFactoryArguments(..)

        Add the given keyword arguments to the arguments used to create new
        step instances;

    .. py:method:: getStepFactory()

        :returns: tuple of (class, keyword arguments)

        Get a factory for new instances of this step.  The step can be created
        by calling the class with the given keyword arguments.

    A few important pieces of information are not available when a step is
    constructed, and are added later.  These are set by the following methods;
    the order in which these methods are called is not defined.

    .. py:method:: setBuild(build)

        :param build: the :class:`~buildbot.process.build.Build` instance
            controlling this step.

        This method is called during setup to set the build instance
        controlling this slave.  Subclasses can override this to get access to
        the build object as soon as it is available.  The default
        implementation sets the :attr:`build` attribute.

    .. py:attribute:: build

        The build object controlling this step.

    .. py:method:: setBuildSlave(build)

        :param build: the :class:`~buildbot.buildslave.BuildSlave` instance on
            which this step will run.

        Similarly, this method is called with the build slave that will run
        this step.  The default implementation sets the :attr:`buildslave`
        attribute.

    .. py:attribute:: buildslave

        The build slave that will run this step.

    .. py:method:: setDefaultWorkdir(workdir)

        :param workdir: the default workdir, from the build

        This method is called at build startup with the default workdir for the
        build.  Steps which allow a workdir to be specified, but want to
        override it with the build's default workdir, can use this method to
        apply the default.

    .. py:method:: setStepStatus(status)

        :param status: step status
        :type status: :class:`~buildbot.status.buildstep.BuildStepStatus`

        This method is called to set the status instance to which the step
        should report.  The default implementation sets :attr:`step_status`.

    .. py:attribute:: step_status

        The :class:`~buildbot.status.buildstep.BuildStepStatus` object tracking
        the status of this step.

    .. py:method:: setupProgress()

        This method is called during build setup to give the step a chance to
        set up progress tracking.  It is only called if the build has
        :attr:`useProgress` set.  There is rarely any reason to override this
        method.

    .. py:attribute:: progress

        If the step is tracking progress, this is a
        :class:`~buildbot.status.progress.StepProgress` instance performing
        that task.

    Exeuction of the step itself is governed by the following methods and attributes.

    .. py:method:: startStep(remote)

        :param remote: a remote reference to the slave-side
            :class:`~buildslave.bot.SlaveBuilder` instance
        :returns: Deferred

        Begin the step. This is the build's interface to step execution.
        Subclasses should override :meth:`start` to implement custom behaviors.

        The method returns a Deferred that fires when the step finishes.  It
        fires with a tuple of ``(result, [extra text])``, where ``result`` is
        one of the constants from :mod:`buildbot.status.builder`.  The extra
        text is a list of short strings which should be appended to the Build's
        text results. For example, a test step may add ``17 failures`` to the
        Build's status by this mechanism.

        The deferred will errback if the step encounters an exception,
        including an exception on the slave side (or if the slave goes away
        altogether). Normal build/test failures will *not* cause an errback.

    .. py:method:: start()

        :returns: ``None`` or :data:`~buildbot.status.results.SKIPPED`

        Begin the step. Subclasses should override this method to do local
        processing, fire off remote commands, etc.  The parent method raises
        :exc:`NotImplementedError`.

        Note that this method does *not* return a Deferred.  When the step is
        done, it should call :meth:`finished`, with a result -- a constant from
        :mod:`buildbot.status.results`.  The result will be handed off to
        the :class:`~buildbot.process.build.Build`.

        If the step encounters an exception, it should call :meth:`failed` with
        a Failure object. This method automatically fails the whole build with
        an exception.  A common idiom is to add :meth:`failed` as an errback on
        a Deferred::

            cmd = LoggedRemoteCommand(args)
            d = self.runCommand(cmd)
            def suceed(_):
                self.finished(results.SUCCESS)
            d.addCallback(succeed)
            d.addErrback(self.failed)

        If the step decides it does not need to be run, :meth:`start` can
        return the constant :data:`~buildbot.status.results.SKIPPED`.  In this
        case, it is not necessary to call :meth:`finished` directly.

    .. py:method:: finished(results)

        :param results: a constant from :mod:`~buildbot.status.results`

        A call to this method indicates that the step is finished and the build
        should analyze the results and perhaps proceed to the next step.  The
        step should not perform any additional processing after calling this
        method.

    .. py:method:: failed(failure)

        :param failure: a :class:`~twisted.python.failure.Failure` instance

        Similar to :meth:`finished`, this method indicates that the step is
        finished, but handles exceptions with appropriate logging and
        diagnostics.

        This method handles :exc:`BuildStepFailed` specially, by calling
        ``finished(FAILURE)``.  This provides subclasses with a shortcut to
        stop execution of a step by raising this failure in a context where
        :meth:`failed` will catch it.

    .. py:method:: interrupt(reason)

        :param reason: why the build was interrupted
        :type reason: string or :class:`~twisted.python.failure.Failure`

        This method is used from various control interfaces to stop a running
        step.  The step should be brought to a halt as quickly as possible, by
        cancelling a remote command, killing a local process, etc.  The step
        must still finish with either :meth:`finished` or :meth:`failed`. 

        The ``reason`` parameter can be a string or, when a slave is lost
        during step processing, a :exc:`~twisted.internet.error.ConnectionLost`
        failure.

        The parent method handles any pending lock operations, and should be
        called by implementations in subclasses.

    .. py:attribute:: stopped

        If false, then the step is running.  If true, the step is not running,
        or has been interrupted.

    This method provides a convenient way to summarize the status of the step
    for status displays:

    .. py:method:: describe(done=False)

        :param done: If true, the step is finished.
        :returns: list of strings

        Describe the step succinctly.  The return value should be a sequence of
        short strings suitable for display in a horizontally constrained space.

        .. note::

            Be careful not to assume that the step has been started in this
            method.  In relatively rare circumstances, steps are described
            before they have started.  Ideally, unit tests should be used to
            ensure that this method is resilient.

    Build steps support progress metrics - values that increase roughly
    linearly during the execution of the step, and can thus be used to
    calculate an expected completion time for a running step.  A metric may be
    a count of lines logged, tests executed, or files compiled.  The build
    mechanics will take care of translating this progress information into an
    ETA for the user.

    .. py:method:: setProgress(metric, value)

        :param metric: the metric to update
        :type metric: string
        :param value: the new value for the metric
        :type value: integer

        Update a progress metric.  This should be called by subclasses that can
        provide useful progress-tracking information. 

        The specified metric name must be included in :attr:`progressMetrics`.

    The following methods are provided as utilities to subclasses.  These
    methods should only be invoked after the step is started.

    .. py:method:: slaveVersion(command, oldVersion=None)

        :param command: command to examine
        :type command: string
        :param oldVersion: return value if the slave does not specify a version
        :returns: string

        Fetch the version of the named command, as specified on the slave.  In
        practice, all commands on a slave have the same version, but passing
        ``command`` is still useful to ensure that the command is implemented
        on the slave.  If the command is not implemented on the slave,
        :meth:`slaveVersion` will return ``None``.

        Versions take the form ``x.y`` where ``x`` and ``y`` are integers, and
        are compared as expected for version numbers.

        Buildbot versions older than 0.5.0 did not support version queries; in
        this case, :meth:`slaveVersion` will return ``oldVersion``.  Since such
        ancient versions of Buildbot are no longer in use, this functionality
        is largely vestigial.

    .. py:method:: slaveVersionIsOlderThan(command, minversion)

        :param command: command to examine
        :type command: string
        :param minversion: minimum version
        :returns: boolean

        This method returns true if ``command`` is not implemented on the
        slave, or if it is older than ``minversion``.

    .. py:method:: getSlaveName()

        :returns: string

        Get the name of the buildslave assigned to this step.

    .. py:method:: runCommand(command)

        :returns: Deferred

        This method connects the given command to the step's buildslave and
        runs it, returning the Deferred from
        :meth:`~buildbot.process.buildstep.RemoteCommand.run`.

    .. py:method:: addURL(name, url)

        :param name: URL name
        :param url: the URL

        Add a link to the given ``url``, with the given ``name`` to displays of
        this step.  This allows a step to provide links to data that is not
        available in the log files.

    The :class:`BuildStep` class provides minimal support for log handling,
    that is extended by the :class:`LoggingBuildStep` class.  The following
    methods provide some useful behaviors.  These methods can be called while
    the step is running, but not before.

    .. py:method:: addLog(name)

        :param name: log name
        :returns: :class:`~buildbot.status.logfile.LogFile` instance

        Add a new logfile with the given name to the step, and return the log
        file instance.

    .. py:method:: getLog(name)

        :param name: log name
        :returns: :class:`~buildbot.status.logfile.LogFile` instance
        :raises: :exc:`KeyError` if the log is not found

        Get an existing logfile by name.

    .. py:method:: addCompleteLog(name, text)

        :param name: log name
        :param text: content of the logfile

        This method adds a new log and sets ``text`` as its content.  This is
        often useful to add a short logfile describing activities performed on
        the master.  The logfile is immediately closed, and no further data can
        be added.

    .. py:method:: addHTMLLog(name, html)

        :param name: log name
        :param html: content of the logfile

        Similar to :meth:`addCompleteLog`, this adds a logfile containing
        pre-formatted HTML, allowing more expressiveness than the text format
        supported by :meth:`addCompleteLog`.

    .. py:method:: addLogObserver(logname, observer)

        :param logname: log name
        :param observer: log observer instance

        Add a log observer for the named log.  The named log need not have been
        added already: the observer will be connected when the log is added.

        See :ref:`Adding-LogObservers` for more information on log observers.

LoggingBuildStep
----------------

.. py:class:: LoggingBuildStep(logfiles, lazylogfiles, log_eval_func, name, locks, haltOnFailure, flunkOnWarnings, flunkOnFailure, warnOnWarnings, warnOnFailure, alwaysRun, progressMetrics, useProgress, doStepIf)

    :param logfiles: see :bb:step:`ShellCommand`
    :param lazylogfiles: see :bb:step:`ShellCommand`
    :param log_eval_func: see :bb:step:`ShellCommand`

    The remaining arguments are passed to the :class:`BuildStep` constructor.

    This subclass of :class:`BuildStep` is designed to help its subclasses run
    remote commands that produce standard I/O logfiles.  It:

    * tracks progress using the length of the stdout logfile
    * provides hooks for summarizing and evaluating the command's result
    * supports lazy logfiles
    * handles the mechanics of starting, interrupting, and finishing remote
      commands
    * detects lost slaves and finishes with a status of
      :data:`~buildbot.status.results.RETRY`

    .. py:attribute:: logfiles

        The logfiles to track, as described for :bb:step:`ShellCommand`.  The
        contents of the class-level ``logfiles`` attribute are combined with
        those passed to the constructor, so subclasses may add log files with a
        class attribute::

            class MyStep(LoggingBuildStep):
                logfiles = dict(debug='debug.log')

        Note that lazy logfiles cannot be specified using this method; they
        must be provided as constructor arguments.

    .. py:method:: startCommand(command)

        :param command: the :class:`~buildbot.process.buildstep.RemoteCommand`
            instance to start

        .. note::

            This method permits an optional ``errorMessages`` parameter,
            allowing errors detected early in the command process to be logged.
            It will be removed, and its use is deprecated.

         Handle all of the mechanics of running the given command.  This sets
         up all required logfiles, keeps status text up to date, and calls the
         utility hooks described below.  When the command is finished, the step
         is finished as well, making this class is unsuitable for steps that
         run more than one command in sequence.

         Subclasses should override
         :meth:`~buildbot.process.buildstep.BuildStep.start` and, after setting
         up an appropriate command, call this method. ::

            def start(self):
                cmd = RemoteShellCommand(..)
                self.startCommand(cmd, warnings)

    To refine the status output, override one or more of the following methods.
    The :class:`LoggingBuildStep` implementations are stubs, so there is no
    need to call the parent method.

    .. py:method:: commandComplete(command)

        :param command: the just-completed remote command

        This is a general-purpose hook method for subclasses. It will be called
        after the remote command has finished, but before any of the other hook
        functions are called.

    .. py:method:: createSummary(stdio)

        :param stdio: stdio :class:`~buildbot.status.logfile.LogFile`

        This hook is designed to perform any summarization of the step, based
        either on the contents of the stdio logfile, or on instance attributes
        set earlier in the step processing.  Implementations of this method
        often call e.g., :meth:`~BuildStep.addURL`.

    .. py:method:: evaluateCommand(command)

        :param command: the just-completed remote command
        :returns: step result from :mod:`buildbot.status.results`

        This hook should decide what result the step should have.  The default
        implementation invokes ``log_eval_func`` if it exists, and looks at
        :attr:`~buildbot.process.buildstep.RemoteCommand.rc` to distinguish
        :data:`~buildbot.status.results.SUCCESS` from
        :data:`~buildbot.status.results.FAILURE`.

    The remaining methods provide an embarassment of ways to set the summary of
    the step that appears in the various status interfaces.  The easiest way to
    affect this output is to override :meth:`~BuildStep.describe`.  If that is
    not flexible enough, override :meth:`getText` and/or :meth:`getText2`.

    .. py:method:: getText(command, results)

        :param command: the just-completed remote command
        :param results: step result from :meth:`evaluateCommand`
        :returns: a list of short strings

        This method is the primary means of describing the step.  The default
        implementation calls :meth:`~BuildStep.describe`, which is usally the
        easiest method to override, and then appends a string describing the
        step status if it was not successful.

    .. py:method:: getText2(command, results)

        :param command: the just-completed remote command
        :param results: step result from :meth:`evaluateCommand`
        :returns: a list of short strings

        Like :meth:`getText`, this method summarizes the step's result, but it
        is only called when that result affects the build, either by making it
        halt, flunk, or end with warnings.

Exceptions
----------

.. py:exception:: BuildStepFailed

    This exception indicates that the buildstep has failed.  It is useful as a
    way to skip all subsequent processing when a step goes wrong.  It is
    handled by :meth:`BuildStep.failed`.
