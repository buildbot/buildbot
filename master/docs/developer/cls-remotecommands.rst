RemoteCommands
==============

.. py:currentmodule:: buildbot.process.remotecommand

Most of the action in build steps consists of performing operations on the worker.
This is accomplished via :class:`RemoteCommand` and its subclasses.
Each represents a single operation on the worker.

Most data is returned to a command via updates.
These updates are described in detail in :ref:`master-worker-updates`.

RemoteCommand
~~~~~~~~~~~~~

.. py:class:: RemoteCommand(remote_command, args, collectStdout=False, ignore_updates=False, decodeRC=dict(0), stdioLogName='stdio')

    :param remote_command: command to run on the worker
    :type remote_command: string
    :param args: arguments to pass to the command
    :type args: dictionary
    :param collectStdout: if True, collect the command's stdout
    :param ignore_updates: true to ignore remote updates
    :param decodeRC: dictionary associating ``rc`` values to buildsteps results constants (e.g. ``SUCCESS``, ``FAILURE``, ``WARNINGS``)
    :param stdioLogName: name of the log to which to write the command's stdio

    This class handles running commands, consisting of a command name and a dictionary of arguments.
    If true, ``ignore_updates`` will suppress any updates sent from the worker.

    This class handles updates for ``stdout``, ``stderr``, and ``header`` by appending them to s stdio logfile named by the ``stdioLogName`` parameter.
    Steps that run multiple commands and want to separate those commands' stdio streams can use this parameter.

    It handles updates for ``rc`` by recording the value in its ``rc`` attribute.

    Most worker-side commands, even those which do not spawn a new process on the worker, generate logs and an ``rc``, requiring this class or one of its subclasses.
    See :ref:`master-worker-updates` for the updates that each command may send.

    .. py:attribute:: active

        True if the command is currently running

    .. py:method:: run(step, remote)

        :param step: the buildstep invoking this command
        :param remote: a reference to the remote :class:`WorkerForBuilder` instance
        :returns: Deferred

        Run the command.
        Call this method to initiate the command; the returned Deferred will fire when the command is complete.
        The Deferred fires with the :class:`RemoteCommand` instance as its value.

    .. py:method:: interrupt(why)

        :param why: reason for interrupt
        :type why: Twisted Failure
        :returns: Deferred

        This method attempts to stop the running command early.
        The Deferred it returns will fire when the interrupt request is received by the worker; this may be a long time before the command itself completes, at which time the Deferred returned from :meth:`run` will fire.

    .. py:method:: results()

        :returns: results constant

        This method checks the ``rc`` against the decodeRC dictionary, and returns results constant

    .. py:method:: didFail()

        :returns: bool

        This method returns True if the results() function returns FAILURE

    The following methods are invoked from the worker.
    They should not be called directly.

    .. py:method:: remote_update(updates)

        :param updates: new information from the worker

        Handles updates from the worker on the running command.
        See :ref:`master-worker-updates` for the content of the updates.
        This class splits the updates out, and handles the ``ignore_updates`` option, then calls :meth:`remoteUpdate` to process the update.

    .. py:method:: remote_complete(failure=None)

        :param failure: the failure that caused the step to complete, or None for success

        Called by the worker to indicate that the command is complete.
        Normal completion (even with a nonzero ``rc``) will finish with no failure; if ``failure`` is set, then the step should finish with status :attr:`~buildbot.process.results.EXCEPTION`.

    These methods are hooks for subclasses to add functionality.

    .. py:method:: remoteUpdate(update)

        :param update: the update to handle

        Handle a single update.  Subclasses must override this method.

    .. py:method:: remoteComplete(failure)

        :param failure: the failure that caused the step to complete, or None for success
        :returns: Deferred

        Handle command completion, performing any necessary cleanup.
        Subclasses should override this method.
        If ``failure`` is not None, it should be returned to ensure proper processing.

    .. py:attribute:: logs

        A dictionary of :class:`~buildbot.status.logfile.LogFile` instances representing active logs.
        Do not modify this directly -- use :meth:`useLog` instead.

    .. py:attribute:: rc

        Set to the return code of the command, after the command has completed.
        For compatibility with shell commands, 0 is taken to indicate success, while nonzero return codes indicate failure.

    .. py:attribute:: stdout

        If the ``collectStdout`` constructor argument is true, then this attribute will contain all data from stdout, as a single string.
        This is helpful when running informational commands (e.g., ``svnversion``), but is not appropriate for commands that will produce a large amount of output, as that output is held in memory.

    To set up logging, use :meth:`useLog` or :meth:`useLogDelayed` before starting the command:

    .. py:method:: useLog(log, closeWhenFinished=False, logfileName=None)

        :param log: the :class:`~buildbot.status.logfile.LogFile` instance to add to.
        :param closeWhenFinished: if true, call :meth:`~buildbot.status.logfile.LogFile.finish` when the command is finished.
        :param logfileName: the name of the logfile, as given to the worker.
                            This is ``stdio`` for standard streams.

        Route log-related updates to the given logfile.
        Note that ``stdio`` is not included by default, and must be added explicitly.
        The ``logfileName`` must match the name given by the worker in any ``log`` updates.

    .. py:method:: useLogDelayed(logfileName, activateCallback, closeWhenFinished=False)

        :param logfileName: the name of the logfile, as given to the worker.
                            This is ``stdio`` for standard streams.
        :param activateCallback: callback for when the log is added; see below
        :param closeWhenFinished: if true, call :meth:`~buildbot.status.logfile.LogFile.finish` when the command is finished.

        Similar to :meth:`useLog`, but the logfile is only actually added when an update arrives for it.
        The callback, ``activateCallback``, will be called with the :class:`~buildbot.process.remotecommand.RemoteCommand` instance when the first update for the log is delivered.
        It should return the desired log instance, optionally via a Deferred.

    With that finished, run the command using the inherited :meth:`~buildbot.process.remotecommand.RemoteCommand.run` method.
    During the run, you can inject data into the logfiles with any of these methods:

    .. py:method:: addStdout(data)

        :param data: data to add to the logfile
        :returns: Deferred

        Add stdout data to the ``stdio`` log.

    .. py:method:: addStderr(data)

        :param data: data to add to the logfile
        :returns: Deferred

        Add stderr data to the ``stdio`` log.

    .. py:method:: addHeader(data)

        :param data: data to add to the logfile
        :returns: Deferred

        Add header data to the ``stdio`` log.

    .. py:method:: addToLog(logname, data)

        :param logname: the logfile to receive the data
        :param data: data to add to the logfile
        :returns: Deferred

        Add data to a logfile other than ``stdio``.

.. py:class:: RemoteShellCommand(workdir, command, env=None, want_stdout=True, want_stderr=True, timeout=20*60, maxTime=None, sigtermTime=None, logfiles={}, usePTY="slave-config", logEnviron=True, collectStdio=False)

    :param workdir: directory in which command should be executed, relative to the builder's basedir.
    :param command: shell command to run
    :type command: string or list
    :param want_stdout: If false, then no updates will be sent for stdout.
    :param want_stderr: If false, then no updates will be sent for stderr.
    :param timeout: Maximum time without output before the command is killed.
    :param maxTime: Maximum overall time from the start before the command is killed.
    :param sigtermTime: Try to kill the command with SIGTERM and wait for sigtermTime seconds before firing SIGKILL.
                        If None, SIGTERM will not be fired.
    :param env: A dictionary of environment variables to augment or replace the existing environment on the worker.
    :param logfiles: Additional logfiles to request from the worker.
    :param usePTY: True to use a PTY, false to not use a PTY; the default value uses the default configured on the worker.
    :param logEnviron: If false, do not log the environment on the worker.
    :param collectStdout: If True, collect the command's stdout.

    Most of the constructor arguments are sent directly to the worker; see :ref:`shell-command-args` for the details of the formats.
    The ``collectStdout`` parameter is as described for the parent class.

    If shell command contains passwords they can be hidden from log files by passing them as tuple in command argument.
    Eg. ``['print', ('obfuscated', 'password', 'dummytext')]`` is logged as ``['print', 'dummytext']``.

    This class is used by the :bb:step:`ShellCommand` step, and by steps that run multiple customized shell commands.
