BuildSteps
==========

.. py:module:: buildbot.process.buildstep

There are a few parent classes that are used as base classes for real buildsteps.
This section describes the base classes.  The "leaf" classes are described in :doc:`../manual/cfg-buildsteps`.

BuildStep
---------

.. py:class:: BuildStep(name, description, descriptionDone, descriptionSuffix, locks, haltOnFailure, flunkOnWarnings, flunkOnFailure, warnOnWarnings, warnOnFailure, alwaysRun, progressMetrics, useProgress, doStepIf, hideStepIf)

    All constructor arguments must be given as keyword arguments.
    Each constructor parameter is copied to the corresponding attribute.

    .. py:attribute:: name

        The name of the step.

    .. py:attribute:: description

        The description of the step.

    .. py:attribute:: descriptionDone

        The description of the step after it has finished.

    .. py:attribute:: descriptionSuffix

        Any extra information to append to the description.

    .. py:attribute:: locks

        List of locks for this step; see :ref:`Interlocks`.

    .. py:attribute:: progressMetrics

        List of names of metrics that should be used to track the progress of this build, and build ETA's for users.
        This is generally set in the

    .. py:attribute:: useProgress

        If true (the default), then ETAs will be calculated for this step using progress metrics.
        If the step is known to have unpredictable timing (e.g., an incremental build), then this should be set to false.

    .. py:attribute:: doStepIf

        A callable or bool to determine whether this step should be executed.
        See :ref:`Buildstep-Common-Parameters` for details.

    .. py:attribute:: hideStepIf

        A callable or bool to determine whether this step should be shown in the waterfall and build details pages.
        See :ref:`Buildstep-Common-Parameters` for details.

    The following attributes affect the behavior of the containing build:

    .. py:attribute:: haltOnFailure

        If true, the build will halt on a failure of this step, and not execute subsequent tests (except those with ``alwaysRun``).

    .. py:attribute:: flunkOnWarnings

        If true, the build will be marked as a failure if this step ends with warnings.

    .. py:attribute:: flunkOnFailure

        If true, the build will be marked as a failure if this step fails.

    .. py:attribute:: warnOnWarnings

        If true, the build will be marked as warnings, or worse, if this step ends with warnings.

    .. py:attribute:: warnOnFailure

        If true, the build will be marked as warnings, or worse, if this step fails.

    .. py:attribute:: alwaysRun

        If true, the step will run even if a previous step halts the build with ``haltOnFailure``.

    A few important pieces of information are not available when a step is constructed, and are added later.
    These are set by the following methods; the order in which these methods are called is not defined.

    .. py:method:: setBuild(build)

        :param build: the :class:`~buildbot.process.build.Build` instance controlling this step.

        This method is called during setup to set the build instance controlling this slave.
        Subclasses can override this to get access to the build object as soon as it is available.
        The default implementation sets the :attr:`build` attribute.

    .. py:attribute:: build

        The build object controlling this step.

    .. py:method:: setBuildSlave(build)

        :param build: the :class:`~buildbot.buildslave.BuildSlave` instance on which this step will run.

        Similarly, this method is called with the build slave that will run this step.
        The default implementation sets the :attr:`buildslave` attribute.

    .. py:attribute:: buildslave

        The build slave that will run this step.

    .. py:method:: setDefaultWorkdir(workdir)

        :param workdir: the default workdir, from the build

        This method is called at build startup with the default workdir for the build.
        Steps which allow a workdir to be specified, but want to override it with the build's default workdir, can use this method to apply the default.

    .. py:method:: setStepStatus(status)

        :param status: step status
        :type status: :class:`~buildbot.status.buildstep.BuildStepStatus`

        This method is called to set the status instance to which the step should report.
        The default implementation sets :attr:`step_status`.

    .. py:attribute:: step_status

        The :class:`~buildbot.status.buildstep.BuildStepStatus` object tracking the status of this step.

    .. py:method:: setupProgress()

        This method is called during build setup to give the step a chance to set up progress tracking.
        It is only called if the build has :attr:`useProgress` set.
        There is rarely any reason to override this method.

    .. py:attribute:: progress

        If the step is tracking progress, this is a :class:`~buildbot.status.progress.StepProgress` instance performing that task.

    Execution of the step itself is governed by the following methods and attributes.

    .. py:method:: startStep(remote)

        :param remote: a remote reference to the slave-side
            :class:`~buildslave.bot.SlaveBuilder` instance
        :returns: Deferred

        Begin the step. This is the build's interface to step execution.
        Subclasses should override :meth:`start` to implement custom behaviors.

        The method returns a Deferred that fires when the step finishes.
        It fires with a tuple of ``(result, [extra text])``, where ``result`` is one of the constants from :mod:`buildbot.status.builder`.
        The extra text is a list of short strings which should be appended to the Build's text results.
        For example, a test step may add ``17 failures`` to the Build's status by this mechanism.

        The deferred will errback if the step encounters an exception, including an exception on the slave side (or if the slave goes away altogether).
        Normal build/test failures will *not* cause an errback.

    .. py:method:: run()

        :returns: result via Deferred

        Execute the step.
        When this method returns (or when the Deferred it returns fires), the step is complete.
        The method's return value must be an integer, giving the result of the step -- a constant from :mod:`buildbot.status.results`.
        If the method raises an exception or its Deferred fires with failure, then the step will be completed with an EXCEPTION result.
        Any other output from the step (logfiles, status strings, URLs, etc.) is the responsibility of the ``run`` method.

        Subclasses should override this method.
        Do *not* call :py:meth:`finished` or :py:meth:`failed` from this method.

    .. py:method:: start()

        :returns: ``None`` or :data:`~buildbot.status.results.SKIPPED`,
            optionally via a Deferred.

        Begin the step.
        BuildSteps written before Buildbot-0.9.0 often override this method instead of :py:meth:`run`, but this approach is deprecated.

        When the step is done, it should call :py:meth:`finished`, with a result -- a constant from :mod:`buildbot.status.results`.
        The result will be handed off to the :py:class:`~buildbot.process.build.Build`.

        If the step encounters an exception, it should call :meth:`failed` with a Failure object.

        If the step decides it does not need to be run, :meth:`start` can return the constant :data:`~buildbot.status.results.SKIPPED`.
        In this case, it is not necessary to call :meth:`finished` directly.

    .. py:method:: finished(results)

        :param results: a constant from :mod:`~buildbot.status.results`

        A call to this method indicates that the step is finished and the build should analyze the results and perhaps proceed to the next step.
        The step should not perform any additional processing after calling this method.
        This method must only be called from the (deprecated) :py:meth:`start` method.

    .. py:method:: failed(failure)

        :param failure: a :class:`~twisted.python.failure.Failure` instance

        Similar to :meth:`finished`, this method indicates that the step is finished, but handles exceptions with appropriate logging and diagnostics.

        This method handles :exc:`BuildStepFailed` specially, by calling ``finished(FAILURE)``.
        This provides subclasses with a shortcut to stop execution of a step by raising this failure in a context where :meth:`failed` will catch it.
        This method must only be called from the (deprecated) :py:meth:`start` method.

    .. py:method:: interrupt(reason)

        :param reason: why the build was interrupted
        :type reason: string or :class:`~twisted.python.failure.Failure`

        This method is used from various control interfaces to stop a running step.
        The step should be brought to a halt as quickly as possible, by cancelling a remote command, killing a local process, etc.
        The step must still finish with either :meth:`finished` or :meth:`failed`.

        The ``reason`` parameter can be a string or, when a slave is lost during step processing, a :exc:`~twisted.internet.error.ConnectionLost` failure.

        The parent method handles any pending lock operations, and should be called by implementations in subclasses.

    .. py:attribute:: stopped

        If false, then the step is running.  If true, the step is not running, or has been interrupted.

    This method provides a convenient way to summarize the status of the step for status displays:

    .. py:method:: describe(done=False)

        :param done: If true, the step is finished.
        :returns: list of strings

        Describe the step succinctly.
        The return value should be a sequence of short strings suitable for display in a horizontally constrained space.

        .. note::

            Be careful not to assume that the step has been started in this method.
            In relatively rare circumstances, steps are described before they have started.
            Ideally, unit tests should be used to ensure that this method is resilient.

    Build steps have statistics, a simple key/value store of data which can later be aggregated over all steps in a build.
    Note that statistics are not preserved after a build is complete.

    .. py:method:: hasStatistic(stat)

        :param string stat: name of the statistic
        :returns: True if the statistic exists on this step

    .. py:method:: getStatistic(stat, default=None)

        :param string stat: name of the statistic
        :param default: default value if the statistic does not exist
        :returns: value of the statistic, or the default value

    .. py:method:: getStatistics()

        :returns: a dictionary of all statistics for this step

    .. py:method:: setStatistic(stat, value)

        :param string stat: name of the statistic
        :param value: value to assign to the statistic
        :returns: value of the statistic

    Build steps support progress metrics - values that increase roughly linearly during the execution of the step, and can thus be used to calculate an expected completion time for a running step.
    A metric may be a count of lines logged, tests executed, or files compiled.
    The build mechanics will take care of translating this progress information into an ETA for the user.

    .. py:method:: setProgress(metric, value)

        :param metric: the metric to update
        :type metric: string
        :param value: the new value for the metric
        :type value: integer

        Update a progress metric.
        This should be called by subclasses that can provide useful progress-tracking information.

        The specified metric name must be included in :attr:`progressMetrics`.

    The following methods are provided as utilities to subclasses.
    These methods should only be invoked after the step is started.

    .. py:method:: slaveVersion(command, oldversion=None)

        :param command: command to examine
        :type command: string
        :param oldversion: return value if the slave does not specify a version
        :returns: string

        Fetch the version of the named command, as specified on the slave.
        In practice, all commands on a slave have the same version, but passing ``command`` is still useful to ensure that the command is implemented on the slave.
        If the command is not implemented on the slave, :meth:`slaveVersion` will return ``None``.

        Versions take the form ``x.y`` where ``x`` and ``y`` are integers, and are compared as expected for version numbers.

        Buildbot versions older than 0.5.0 did not support version queries; in this case, :meth:`slaveVersion` will return ``oldVersion``.
        Since such ancient versions of Buildbot are no longer in use, this functionality is largely vestigial.

    .. py:method:: slaveVersionIsOlderThan(command, minversion)

        :param command: command to examine
        :type command: string
        :param minversion: minimum version
        :returns: boolean

        This method returns true if ``command`` is not implemented on the slave, or if it is older than ``minversion``.

    .. py:method:: getSlaveName()

        :returns: string

        Get the name of the buildslave assigned to this step.

    Most steps exist to run commands.
    While the details of exactly how those commands are constructed are left to subclasses, the execution of those commands comes down to this method:

    .. py:method:: runCommand(command)

        :param command: :py:class:`~buildbot.process.remotecommand.RemoteCommand` instance
        :returns: Deferred

        This method connects the given command to the step's buildslave and runs it, returning the Deferred from :meth:`~buildbot.process.buildstep.RemoteCommand.run`.

    .. py:method:: addURL(name, url)

        :param name: URL name
        :param url: the URL

        Add a link to the given ``url``, with the given ``name`` to displays of this step.
        This allows a step to provide links to data that is not available in the log files.

    The :class:`BuildStep` class provides minimal support for log handling, that is extended by the :class:`LoggingBuildStep` class.
    The following methods provide some useful behaviors.
    These methods can be called while the step is running, but not before.

    .. py:method:: addLog(name)

        :param name: log name
        :returns: :class:`~buildbot.status.logfile.LogFile` instance

        Add a new logfile with the given name to the step, and return the log file instance.

    .. py:method:: getLog(name)

        :param name: log name
        :returns: :class:`~buildbot.status.logfile.LogFile` instance
        :raises: :exc:`KeyError` if the log is not found

        Get an existing logfile by name.

    .. py:method:: addCompleteLog(name, text)

        :param name: log name
        :param text: content of the logfile

        This method adds a new log and sets ``text`` as its content.
        This is often useful to add a short logfile describing activities performed on the master.
        The logfile is immediately closed, and no further data can be added.

    .. py:method:: addHTMLLog(name, html)

        :param name: log name
        :param html: content of the logfile

        Similar to :meth:`addCompleteLog`, this adds a logfile containing pre-formatted HTML, allowing more expressiveness than the text format supported by :meth:`addCompleteLog`.

    .. py:method:: addLogObserver(logname, observer)

        :param logname: log name
        :param observer: log observer instance

        Add a log observer for the named log.
        The named log need not have been added already: the observer will be connected when the log is added.

        See :ref:`Adding-LogObservers` for more information on log observers.

    .. py:method:: setStateStrings(strings)

        :param strings: a list of short strings
        :returns: Deferred

        Update the state strings associated with this step.
        This completely replaces any previously-set state strings.
        This method replaces ``self.step_status.setText`` and ``self.step_status.setText2`` in new-style steps.

LoggingBuildStep
----------------

.. py:class:: LoggingBuildStep(logfiles, lazylogfiles, log_eval_func, name, locks, haltOnFailure, flunkOnWarnings, flunkOnFailure, warnOnWarnings, warnOnFailure, alwaysRun, progressMetrics, useProgress, doStepIf, hideStepIf)

    :param logfiles: see :bb:step:`ShellCommand`
    :param lazylogfiles: see :bb:step:`ShellCommand`
    :param log_eval_func: see :bb:step:`ShellCommand`

    The remaining arguments are passed to the :class:`BuildStep` constructor.

    This subclass of :class:`BuildStep` is designed to help its subclasses run remote commands that produce standard I/O logfiles.
    It:

    * tracks progress using the length of the stdout logfile
    * provides hooks for summarizing and evaluating the command's result
    * supports lazy logfiles
    * handles the mechanics of starting, interrupting, and finishing remote commands
    * detects lost slaves and finishes with a status of
      :data:`~buildbot.status.results.RETRY`

    .. py:attribute:: logfiles

        The logfiles to track, as described for :bb:step:`ShellCommand`.
        The contents of the class-level ``logfiles`` attribute are combined with those passed to the constructor, so subclasses may add log files with a class attribute::

            class MyStep(LoggingBuildStep):
                logfiles = dict(debug='debug.log')

        Note that lazy logfiles cannot be specified using this method; they must be provided as constructor arguments.

    .. py:method:: startCommand(command)

        :param command: the :class:`~buildbot.process.buildstep.RemoteCommand`
            instance to start

        .. note::

            This method permits an optional ``errorMessages`` parameter, allowing errors detected early in the command process to be logged.
            It will be removed, and its use is deprecated.

         Handle all of the mechanics of running the given command.
         This sets up all required logfiles, keeps status text up to date, and calls the utility hooks described below.
         When the command is finished, the step is finished as well, making this class is unsuitable for steps that run more than one command in sequence.

         Subclasses should override :meth:`~buildbot.process.buildstep.BuildStep.start` and, after setting up an appropriate command, call this method. ::

            def start(self):
                cmd = RemoteShellCommand(...)
                self.startCommand(cmd, warnings)

    To refine the status output, override one or more of the following methods.
    The :class:`LoggingBuildStep` implementations are stubs, so there is no need to call the parent method.

    .. py:method:: commandComplete(command)

        :param command: the just-completed remote command

        This is a general-purpose hook method for subclasses.
        It will be called after the remote command has finished, but before any of the other hook functions are called.

    .. py:method:: createSummary(stdio)

        :param stdio: stdio :class:`~buildbot.status.logfile.LogFile`

        This hook is designed to perform any summarization of the step, based either on the contents of the stdio logfile, or on instance attributes set earlier in the step processing.
        Implementations of this method often call e.g., :meth:`~BuildStep.addURL`.

    .. py:method:: evaluateCommand(command)

        :param command: the just-completed remote command
        :returns: step result from :mod:`buildbot.status.results`

        This hook should decide what result the step should have.
        The default implementation invokes ``log_eval_func`` if it exists, and looks at :attr:`~buildbot.process.buildstep.RemoteCommand.rc` to distinguish :data:`~buildbot.status.results.SUCCESS` from :data:`~buildbot.status.results.FAILURE`.

    The remaining methods provide an embarrassment of ways to set the summary of the step that appears in the various status interfaces.
    The easiest way to affect this output is to override :meth:`~BuildStep.describe`.
    If that is not flexible enough, override :meth:`getText` and/or :meth:`getText2`.

    .. py:method:: getText(command, results)

        :param command: the just-completed remote command
        :param results: step result from :meth:`evaluateCommand`
        :returns: a list of short strings

        This method is the primary means of describing the step.
        The default implementation calls :meth:`~BuildStep.describe`, which is usually the easiest method to override, and then appends a string describing the step status if it was not successful.

    .. py:method:: getText2(command, results)

        :param command: the just-completed remote command
        :param results: step result from :meth:`evaluateCommand`
        :returns: a list of short strings

        Like :meth:`getText`, this method summarizes the step's result, but it is only called when that result affects the build, either by making it halt, flunk, or end with warnings.

CommandMixin
------------

The :py:meth:`~buildbot.process.buildstep.BuildStep.runCommand` method can run a :py:class:`~buildbot.process.remotecommand.RemoteCommand` instance, but it's no help in building that object or interpreting the results afterward.
This mixin class adds some useful methods for running commands.

This class can only be used in new-style steps.

.. py:class:: buildbot.process.buildstep.CommandMixin

    Some remote commands are simple enough that they can boil down to a method call.
    Most of these take an ``abandonOnFailure`` argument which, if true, will abandon the entire buildstep on command failure.
    This is accomplished by raising :py:exc:`~buildbot.process.buildstep.BuildStepFailed`.

    These methods all write to the ``stdio`` log (generally just for errors).
    They do not close the log when finished.

    .. py:method:: runRmdir(dir, abandonOnFailure=True)

        :param dir: directory to remove
        :param abndonOnFailure: if true, abandon step on failure
        :returns: Boolean via Deferred

        Remove the given directory, using the ``rmdir`` command.
        Returns False on failure.

    .. py:method:: runMkdir(dir, abandonOnFailure=True)

        :param dir: directory to create
        :param abndonOnFailure: if true, abandon step on failure
        :returns: Boolean via Deferred

        Create the given directory and any parent directories, using the ``mkdir`` command.
        Returns False on failure.

    .. py:method:: pathExists(path)

        :param path path to test
        :returns: Boolean via Deferred

        Determine if the given path exists on the slave (in any form - file, directory, or otherwise).
        This uses the ``stat`` command.

    .. py:method:: glob(path)

        :param path path to test
        :returns: list of filenames

        Get the list of files matching the given path pattern on the slave.
        This uses Python's ``glob`` module.
        If the ``glob`` method fails, it aborts the step.


ShellMixin
----------

Most Buildbot steps run shell commands on the slave, and Buildbot has an impressive array of configuration parameters to control that execution.
The ``ShellMixin`` mixin provides the tools to make running shell commands easy and flexible.

This class can only be used in new-style steps.

.. py:class:: buildbot.process.buildstep.ShellMixin

    This mixin manages the following step configuration parameters, the contents of which are documented in the manual.
    Naturally, all of these are renderable.

    ..py:attribute:: command
    ..py:attribute:: workdir
    ..py:attribute:: env
    ..py:attribute:: want_stdout
    ..py:attribute:: want_stderr
    ..py:attribute:: usePTY
    ..py:attribute:: logfiles
    ..py:attribute:: lazylogfiles
    ..py:attribute:: timeout
    ..py:attribute:: maxTime
    ..py:attribute:: logEnviron
    ..py:attribute:: interruptSignal
    ..py:attribute:: sigtermTime
    ..py:attribute:: initialStdin
    ..py:attribute:: decodeRC

    ..py:method:: setupShellMixin(constructorArgs, prohibitArgs=[])

        :param dict constructorArgs constructor keyword arguments
        :param list prohibitArgs list of recognized arguments to reject
        :returns: keyword arguments destined for :py:class:`BuildStep`

        This method is intended to be called from the shell constructor, passed any keyword arguments not otherwise used by the step.
        Any attributes set on the instance already (e.g., class-level attributes) are used as defaults.
        Attributes named in ``prohibitArgs`` are rejected with a configuration error.

        The return value should be passed to the :py:class:`BuildStep` constructor.

    ..py:method:: makeRemoteShellCommand(collectStdout=False, collectStderr=False, \**overrides)

        :param collectStdout: if true, the command's stdout wil be available in ``cmd.stdout`` on completion
        :param collectStderr: if true, the command's stderr wil be available in ``cmd.stderr`` on completion
        :param overrides: overrides arguments that might have been passed to :py:meth:`setupShellMixin`
        :returns: :py:class:`~buildbot.process.remotecommand.RemoteShellCommand` instance via Deferred

        This method constructs a :py:class:`~buildbot.process.remotecommand.RemoteShellCommand` instance based on the instance attributes and any supplied overrides.
        It must be called while the step is running, as it examines the slave capabilities before creating the command.
        It takes care of just about everything:

         * Creating log files and associating them with the command
         * Merging environment configuration
         * Selecting the appropriate workdir configuration

        All that remains is to run the command with :py:meth:`~buildbot.process.buildstep.BuildStep.runCommand`.

Exceptions
----------

.. py:exception:: BuildStepFailed

    This exception indicates that the buildstep has failed.
    It is useful as a way to skip all subsequent processing when a step goes wrong.
    It is handled by :meth:`BuildStep.failed`.
