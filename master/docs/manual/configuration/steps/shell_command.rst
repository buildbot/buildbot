.. bb:step:: ShellCommand

.. _Step-ShellCommand:

ShellCommand
------------

Most interesting steps involve executing a process of some sort on the worker.
The :bb:step:`ShellCommand` class handles this activity.

Several subclasses of :bb:step:`ShellCommand` are provided as starting points for common build steps.

Using ShellCommands
+++++++++++++++++++

.. py:class:: buildbot.steps.shell.ShellCommand

This is a useful base class for just about everything you might want to do during a build (except for the initial source checkout).
It runs a single command in a child shell on the worker.
All stdout/stderr is recorded into a :class:`LogFile`.
The step usually finishes with a status of ``FAILURE`` if the command's exit code is non-zero, otherwise it has a status of ``SUCCESS``.

The preferred way to specify the command is with a list of argv strings, since this allows for spaces in filenames and avoids doing any fragile shell-escaping.
You can also specify the command with a single string, in which case the string is given to :samp:`/bin/sh -c {COMMAND}` for parsing.

On Windows, commands are run via ``cmd.exe /c`` which works well.
However, if you're running a batch file, the error level does not get propagated correctly unless you add 'call' before your batch file's name: ``cmd=['call', 'myfile.bat', ...]``.

The :bb:step:`ShellCommand` arguments are:

``command``
    A list of strings (preferred) or single string (discouraged) which specifies the command to be run.
    A list of strings is preferred because it can be used directly as an argv array.
    Using a single string (with embedded spaces) requires the worker to pass the string to :command:`/bin/sh` for interpretation, which raises all sorts of difficult questions about how to escape or interpret shell metacharacters.

    If ``command`` contains nested lists (for example, from a properties substitution), then that list will be flattened before it is executed.

``workdir``
    All :class:`ShellCommand`\s are run by default in the ``workdir``, which defaults to the :file:`build` subdirectory of the worker builder's base directory.
    The absolute path of the workdir will thus be the worker's basedir (set as an option to ``buildbot-worker create-worker``, :ref:`Creating-a-worker`), plus the builder's basedir (set in the builder's ``builddir`` key in :file:`master.cfg`), plus the workdir itself (a class-level attribute of the BuildFactory, defaults to :file:`build`).

    For example:

    .. code-block:: python

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(command=["make", "test"],
                                     workdir="build/tests"))

``env``
    A dictionary of environment strings which will be added to the child command's environment.
    For example, to run tests with a different i18n language setting, you might use:

    .. code-block:: python

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(command=["make", "test"],
                                     env={'LANG': 'fr_FR'}))

    These variable settings will override any existing ones in the worker's environment or the environment specified in the :class:`Builder`.
    The exception is :envvar:`PYTHONPATH`, which is merged with (actually prepended to) any existing :envvar:`PYTHONPATH` setting.
    The following example will prepend :file:`/home/buildbot/lib/python` to any existing :envvar:`PYTHONPATH`:

    .. code-block:: python

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(
                      command=["make", "test"],
                      env={'PYTHONPATH': "/home/buildbot/lib/python"}))

    To avoid the need of concatenating paths together in the master config file, if the value is a list, it will be joined together using the right platform dependent separator.

    Those variables support expansion so that if you just want to prepend :file:`/home/buildbot/bin` to the :envvar:`PATH` environment variable, you can do it by putting the value ``${PATH}`` at the end of the value like in the example below.
    Variables that don't exist on the worker will be replaced by ``""``.

    .. code-block:: python

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(
                      command=["make", "test"],
                      env={'PATH': ["/home/buildbot/bin",
                                    "${PATH}"]}))

    Note that environment values must be strings (or lists that are turned into strings).
    In particular, numeric properties such as ``buildnumber`` must be substituted using :ref:`Interpolate`.

``want_stdout``
    If ``False``, stdout from the child process is discarded rather than being sent to the buildmaster for inclusion in the step's :class:`LogFile`.

``want_stderr``
    Like ``want_stdout`` but for :file:`stderr`.
    Note that commands that run through a PTY do not have separate :file:`stdout`/:file:`stderr` streams, and both are merged into :file:`stdout`.

``usePTY``
    If ``True``, this command will be run in a ``pty`` (defaults to ``False``).
    This option is not available on Windows.

    In general, you do not want to use a pseudo-terminal.
    This is *only* useful for running commands that require a terminal - for example, testing a command-line application that will only accept passwords read from a terminal.
    Using a pseudo-terminal brings lots of compatibility problems, and prevents Buildbot from distinguishing the standard error (red) and standard output (black) streams.

    In previous versions, the advantage of using a pseudo-terminal was that ``grandchild`` processes were more likely to be cleaned up if the build was interrupted or it timed out.
    This occurred because using a pseudo-terminal incidentally puts the command into its own process group.

    As of Buildbot-0.8.4, all commands are placed in process groups, and thus grandchild processes will be cleaned up properly.

``logfiles``
    Sometimes commands will log interesting data to a local file, rather than emitting everything to stdout or stderr.
    For example, Twisted's :command:`trial` command (which runs unit tests) only presents summary information to stdout, and puts the rest into a file named :file:`_trial_temp/test.log`.
    It is often useful to watch these files as the command runs, rather than using :command:`/bin/cat` to dump their contents afterwards.

    The ``logfiles=`` argument allows you to collect data from these secondary logfiles in near-real-time, as the step is running.
    It accepts a dictionary which maps from a local Log name (which is how the log data is presented in the build results) to either a remote filename (interpreted relative to the build's working directory), or a dictionary of options.
    Each named file will be polled on a regular basis (every couple of seconds) as the build runs, and any new text will be sent over to the buildmaster.

    If you provide a dictionary of options instead of a string, you must specify the ``filename`` key.
    You can optionally provide a ``follow`` key which is a boolean controlling whether a logfile is followed or concatenated in its entirety.
    Following is appropriate for logfiles to which the build step will append, where the pre-existing contents are not interesting.
    The default value for ``follow`` is ``False``, which gives the same behavior as just providing a string filename.

    .. code-block:: python

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(
                           command=["make", "test"],
                           logfiles={"triallog": "_trial_temp/test.log"}))

    The above example will add a log named 'triallog' on the master, based on :file:`_trial_temp/test.log` on the worker.

    .. code-block:: python

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(command=["make", "test"],
                                     logfiles={
                                         "triallog": {
                                            "filename": "_trial_temp/test.log",
                                            "follow": True
                                         }
                                     }))


``lazylogfiles``
    If set to ``True``, logfiles will be tracked lazily, meaning that they will only be added when and if something is written to them.
    This can be used to suppress the display of empty or missing log files.
    The default is ``False``.

``timeout``
    If the command fails to produce any output for this many seconds, it is assumed to be locked up and will be killed.
    This defaults to 1200 seconds.
    Pass ``None`` to disable.

``maxTime``
    If the command takes longer than this many seconds, it will be killed.
    This is disabled by default.

``logEnviron``
    If ``True`` (the default), then the step's logfile will describe the environment variables on the worker.
    In situations where the environment is not relevant and is long, it may be easier to set it to ``False``.

``interruptSignal``
    This is the signal (specified by name) that should be sent to the process when the command needs to be interrupted (either by the buildmaster, a timeout, etc.).
    By default, this is "KILL" (9).
    Specify "TERM" (15) to give the process a chance to cleanup.
    This functionality requires a version 0.8.6 worker or newer.

``sigtermTime``
    If set, when interrupting, try to kill the command with SIGTERM and wait for sigtermTime seconds before firing ``interuptSignal``.
    If None, ``interruptSignal`` will be fired immediately upon interrupt.

``initialStdin``
    If the command expects input on stdin, the input can be supplied as a string with this parameter.
    This value should not be excessively large, as it is handled as a single string throughout Buildbot -- for example, do not pass the contents of a tarball with this parameter.

``decodeRC``
    This is a dictionary that decodes exit codes into results value.
    For example, ``{0:SUCCESS,1:FAILURE,2:WARNINGS}`` will treat the exit code ``2`` as ``WARNINGS``.
    The default (``{0:SUCCESS}``) is to treat just 0 as successful.
    Any exit code not present in the dictionary will be treated as ``FAILURE``.
