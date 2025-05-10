.. _Writing-New-BuildSteps:

Writing New BuildSteps
----------------------

.. warning::

   The API of writing custom build steps has changed significantly in Buildbot-0.9.0.
   See :ref:`New-Style-Build-Steps` for details about what has changed since pre 0.9.0 releases.
   This section documents new-style steps.

While it is a good idea to keep your build process self-contained in the source code tree,
sometimes it is convenient to put more intelligence into your Buildbot configuration. One way to do
this is to write a custom :class:`~buildbot.process.buildstep.BuildStep`. Once written, this Step
can be used in the :file:`master.cfg` file.

The best reason for writing a custom :class:`BuildStep` is to better parse the results of the
command being run. For example, a :class:`~buildbot.process.buildstep.BuildStep` that knows about
JUnit could look at the logfiles to determine which tests had been run, how many passed and how
many failed, and then report more detailed information than a simple ``rc==0`` -based `good/bad`
decision.

Buildbot has acquired a large fleet of build steps, and sports a number of knobs and hooks to make
steps easier to write. This section may seem a bit overwhelming, but most custom steps will only
need to apply one or two of the techniques outlined here.

For complete documentation of the build step interfaces, see :doc:`../../developer/cls-buildsteps`.

.. _Writing-BuildStep-Constructors:

Writing BuildStep Constructors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Build steps act as their own factories, so their constructors are a bit more complex than
necessary. The configuration file instantiates a :class:`~buildbot.process.buildstep.BuildStep`
object, but the step configuration must be re-used for multiple builds, so Buildbot needs some way
to create more steps.

Consider the use of a :class:`BuildStep` in :file:`master.cfg`:

.. code-block:: python

    f.addStep(MyStep(someopt="stuff", anotheropt=1))

This creates a single instance of class ``MyStep``. However, Buildbot needs a new object each time
the step is executed. An instance of :class:`~buildbot.process.buildstep.BuildStep` remembers how
it was constructed, and can create copies of itself. When writing a new step class, then, keep in
mind that you cannot do anything "interesting" in the constructor -- limit yourself to checking and
storing arguments.

It is customary to call the parent class's constructor with all otherwise-unspecified keyword arguments.
Keep a ``**kwargs`` argument on the end of your options, and pass that up to the parent class's constructor.

The whole thing looks like this:

.. code-block:: python

    class Frobnify(BuildStep):
        def __init__(self,
                frob_what="frobee",
                frob_how_many=None,
                frob_how=None,
                **kwargs):

            # check
            if frob_how_many is None:
                raise TypeError("Frobnify argument how_many is required")

            # override a parent option
            kwargs['parentOpt'] = 'xyz'

            # call parent
            super().__init__(**kwargs)

            # set Frobnify attributes
            self.frob_what = frob_what
            self.frob_how_many = how_many
            self.frob_how = frob_how

    class FastFrobnify(Frobnify):
        def __init__(self,
                speed=5,
                **kwargs):
            super().__init__(**kwargs)
            self.speed = speed

Step Execution Process
~~~~~~~~~~~~~~~~~~~~~~

A step's execution occurs in its :py:meth:`~buildbot.process.buildstep.BuildStep.run` method. When
this method returns (more accurately, when the Deferred it returns fires), the step is complete.
The method's result must be an integer, giving the result of the step. Any other output from the
step (logfiles, status strings, URLs, etc.) is the responsibility of the ``run`` method.

The :bb:step:`ShellCommand` class implements this ``run`` method, and in most cases steps
subclassing ``ShellCommand`` simply implement some of the subsidiary methods that its ``run``
method calls.

Running Commands
~~~~~~~~~~~~~~~~

To spawn a command in the worker, create a :class:`~buildbot.process.remotecommand.RemoteCommand`
instance in your step's ``run`` method and run it with
:meth:`~buildbot.process.remotecommand.BuildStep.runCommand`:

.. code-block:: python

    cmd = RemoteCommand(args)
    d = self.runCommand(cmd)

The :py:class:`~buildbot.process.buildstep.CommandMixin` class offers a simple interface to several
common worker-side commands.

For the much more common task of running a shell command on the worker, use
:py:class:`~buildbot.process.buildstep.ShellMixin`. This class provides a method to handle the
myriad constructor arguments related to shell commands, as well as a method to create new
:py:class:`~buildbot.process.remotecommand.RemoteCommand` instances. This mixin is the recommended
method of implementing custom shell-based steps. For simple steps that don't involve much logic the
`:bb:step:`ShellCommand` is recommended.

A simple example of a step using the shell mixin is:

.. code-block:: python

    class RunCleanup(buildstep.ShellMixin, buildstep.BuildStep):
        def __init__(self, cleanupScript='./cleanup.sh', **kwargs):
            self.cleanupScript = cleanupScript
            kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
            super().__init__(**kwargs)

        @defer.inlineCallbacks
        def run(self):
            cmd = yield self.makeRemoteShellCommand(
                    command=[self.cleanupScript])
            yield self.runCommand(cmd)
            if cmd.didFail():
                cmd = yield self.makeRemoteShellCommand(
                        command=[self.cleanupScript, '--force'],
                        logEnviron=False)
                yield self.runCommand(cmd)
            return cmd.results()

    @defer.inlineCallbacks
    def run(self):
        cmd = RemoteCommand(args)
        log = yield self.addLog('output')
        cmd.useLog(log, closeWhenFinished=True)
        yield self.runCommand(cmd)

Updating Status Strings
~~~~~~~~~~~~~~~~~~~~~~~

Each step can summarize its current status in a very short string.
For example, a compile step might display the file being compiled.
This information can be helpful to users eager to see their build finish.

Similarly, a build has a set of short strings collected from its steps summarizing the overall
state of the build. Useful information here might include the number of tests run, but probably not
the results of a ``make clean`` step.

As a step runs, Buildbot calls its
:py:meth:`~buildbot.process.buildstep.BuildStep.getCurrentSummary` method as necessary to get the
step's current status. "As necessary" is determined by calls to
:py:meth:`buildbot.process.buildstep.BuildStep.updateSummary`. Your step should call this method
every time the status summary may have changed. Buildbot will take care of rate-limiting summary
updates.

When the step is complete, Buildbot calls its
:py:meth:`~buildbot.process.buildstep.BuildStep.getResultSummary` method to get a final summary of
the step along with a summary for the build.

About Logfiles
~~~~~~~~~~~~~~

Each BuildStep has a collection of log files. Each one has a short name, like `stdio` or
`warnings`. Each log file contains an arbitrary amount of text, usually the contents of some output
file generated during a build or test step, or a record of everything that was printed to
:file:`stdout`/:file:`stderr` during the execution of some command.

Each can contain multiple `channels`, generally limited to three basic ones: stdout, stderr, and
`headers`. For example, when a shell command runs, it writes a few lines to the headers channel to
indicate the exact argv strings being run, which directory the command is being executed in, and
the contents of the current environment variables. Then, as the command runs, it adds a lot of
:file:`stdout` and :file:`stderr` messages. When the command finishes, a final `header` line is
added with the exit code of the process.

Status display plugins can format these different channels in different ways. For example, the web
page shows log files as text/html, with header lines in blue text, stdout in black, and stderr in
red. A different URL is available which provides a text/plain format, in which stdout and stderr
are collapsed together, and header lines are stripped completely. This latter option makes it easy
to save the results to a file and run :command:`grep` or whatever against the output.

Writing Log Files
~~~~~~~~~~~~~~~~~

Most commonly, logfiles come from commands run on the worker. Internally, these are configured by
supplying the :class:`~buildbot.process.remotecommand.RemoteCommand` instance with log files via
the :meth:`~buildbot.process.remoteCommand.RemoteCommand.useLog` method:

.. code-block:: python

    @defer.inlineCallbacks
    def run(self):
        ...
        log = yield self.addLog('stdio')
        cmd.useLog(log, closeWhenFinished=True, 'stdio')
        yield self.runCommand(cmd)

The name passed to :meth:`~buildbot.process.remoteCommand.RemoteCommand.useLog` must match that
configured in the command. In this case, ``stdio`` is the default.

If the log file was already added by another part of the step, it can be retrieved with
:meth:`~buildbot.process.buildstep.BuildStep.getLog`:

.. code-block:: python

    stdioLog = self.getLog('stdio')

Less frequently, some master-side processing produces a log file. If this log file is short and
easily stored in memory, this is as simple as a call to
:meth:`~buildbot.process.buildstep.BuildStep.addCompleteLog`:

.. code-block:: python

    @defer.inlineCallbacks
    def run(self):
        ...
        summary = u'\n'.join('%s: %s' % (k, count)
                             for (k, count) in self.lint_results.items())
        yield self.addCompleteLog('summary', summary)

Note that the log contents must be a unicode string.

Longer logfiles can be constructed line-by-line using the ``add`` methods of the log file:

.. code-block:: python

    @defer.inlineCallbacks
    def run(self):
        ...
        updates = yield self.addLog('updates')
        while True:
            ...
            yield updates.addStdout(some_update)

Again, note that the log input must be a unicode string.

Finally, :meth:`~buildbot.process.buildstep.BuildStep.addHTMLLog` is similar to
:meth:`~buildbot.process.buildstep.BuildStep.addCompleteLog`, but the resulting log will be tagged
as containing HTML. The web UI will display the contents of the log using the browser.

The ``logfiles=`` argument to :bb:step:`ShellCommand` and its subclasses creates new log files and
fills them in realtime by asking the worker to watch an actual file on disk. The worker will look
for additions in the target file and report them back to the :class:`BuildStep`. These additions
will be added to the log file by calling :meth:`addStdout`.

All log files can be used as the source of a :class:`~buildbot.process.logobserver.LogObserver`
just like the normal :file:`stdio` :class:`LogFile`. In fact, it's possible for one
:class:`~buildbot.process.logobserver.LogObserver` to observe a logfile created by another.

Reading Logfiles
~~~~~~~~~~~~~~~~

For the most part, Buildbot tries to avoid loading the contents of a log file into memory as a
single string. For large log files on a busy master, this behavior can quickly consume a great deal
of memory.

Instead, steps should implement a :class:`~buildbot.process.logobserver.LogObserver` to examine log
files one chunk or line at a time.

For commands which only produce a small quantity of output,
:class:`~buildbot.process.remotecommand.RemoteCommand` will collect the command's stdout into its
:attr:`~buildbot.process.remotecommand.RemoteCommand.stdout` attribute if given the
``collectStdout=True`` constructor argument.

.. _Adding-LogObservers:

Adding LogObservers
~~~~~~~~~~~~~~~~~~~

Most shell commands emit messages to stdout or stderr as they operate, especially if you ask them
nicely with a option `--verbose` flag of some sort. They may also write text to a log file while
they run. Your :class:`BuildStep` can watch this output as it arrives, to keep track of how much
progress the command has made or to process log output for later summarization.

To accomplish this, you will need to attach a :class:`~buildbot.process.logobserver.LogObserver` to
the log. This observer is given all text as it is emitted from the command, and has the opportunity
to parse that output incrementally.

There are a number of pre-built :class:`~buildbot.process.logobserver.LogObserver` classes that you
can choose from (defined in :mod:`buildbot.process.buildstep`, and of course you can subclass them
to add further customization. The :class:`LogLineObserver` class handles the grunt work of
buffering and scanning for end-of-line delimiters, allowing your parser to operate on complete
:file:`stdout`/:file:`stderr` lines.

For example, let's take a look at the :class:`TrialTestCaseCounter`, which is used by the
:bb:step:`Trial` step to count test cases as they are run. As Trial executes, it emits lines like
the following:

.. code-block:: none

    buildbot.test.test_config.ConfigTest.testDebugPassword ... [OK]
    buildbot.test.test_config.ConfigTest.testEmpty ... [OK]
    buildbot.test.test_config.ConfigTest.testIRC ... [FAIL]
    buildbot.test.test_config.ConfigTest.testLocks ... [OK]

When the tests are finished, trial emits a long line of `======` and then some lines which
summarize the tests that failed. We want to avoid parsing these trailing lines, because their
format is less well-defined than the `[OK]` lines.

A simple version of the parser for this output looks like this.
The full version is in :src:`master/buildbot/steps/python_twisted.py`.

.. code-block:: python

    from buildbot.plugins import util

    class TrialTestCaseCounter(util.LogLineObserver):
        _line_re = re.compile(r'^([\w\.]+) \.\.\. \[([^\]]+)\]$')
        numTests = 0
        finished = False

        def outLineReceived(self, line):
            if self.finished:
                return
            if line.startswith("=" * 40):
                self.finished = True
                return

            m = self._line_re.search(line.strip())
            if m:
                testname, result = m.groups()
                self.numTests += 1
                self.step.setProgress('tests', self.numTests)

This parser only pays attention to stdout, since that's where trial writes the progress lines. It
has a mode flag named ``finished`` to ignore everything after the ``====`` marker, and a
scary-looking regular expression to match each line while hopefully ignoring other messages that
might get displayed as the test runs.

Each time it identifies that a test has been completed, it increments its counter and delivers the
new progress value to the step with ``self.step.setProgress``. This helps Buildbot to determine the
ETA for the step.

To connect this parser into the :bb:step:`Trial` build step, ``Trial.__init__`` ends with the following clause:

.. code-block:: python

    # this counter will feed Progress along the 'test cases' metric
    counter = TrialTestCaseCounter()
    self.addLogObserver('stdio', counter)
    self.progressMetrics += ('tests',)

This creates a :class:`TrialTestCaseCounter` and tells the step that the counter wants to watch the
:file:`stdio` log. The observer is automatically given a reference to the step in its :attr:`step`
attribute.

Using Properties
~~~~~~~~~~~~~~~~

In custom :class:`BuildSteps`, you can get and set the build properties with the
:meth:`getProperty` and :meth:`setProperty` methods. Each takes a string for the name of the
property, and returns or accepts an arbitrary JSON-able (lists, dicts, strings, and numbers)
object. For example:

.. code-block:: python

    class MakeTarball(buildstep.ShellMixin, buildstep.BuildStep):
        def __init__(self, **kwargs):
            kwargs = self.setupShellMixin(kwargs)
            super().__init__(**kwargs)

        @defer.inlineCallbacks
        def run(self):
            if self.getProperty("os") == "win":
                # windows-only command
                cmd = yield self.makeRemoteShellCommand(commad=[ ... ])
            else:
                # equivalent for other systems
                cmd = yield self.makeRemoteShellCommand(commad=[ ... ])
            yield self.runCommand(cmd)
            return cmd.results()


Remember that properties set in a step may not be available until the next step begins. In
particular, any :class:`Property` or :class:`Interpolate` instances for the current step are
interpolated before the step starts, so they cannot use the value of any properties determined in
that step.

.. index:: links, BuildStep URLs, addURL

Using Statistics
~~~~~~~~~~~~~~~~

Statistics can be generated for each step, and then summarized across all steps in a build. For
example, a test step might set its ``warnings`` statistic to the number of warnings observed. The
build could then sum the ``warnings`` on all steps to get a total number of warnings.

Statistics are set and retrieved with the
:py:meth:`~buildbot.process.buildstep.BuildStep.setStatistic` and
:py:meth:`~buildbot.process.buildstep.BuildStep.getStatistic` methods. The
:py:meth:`~buildbot.process.buildstep.BuildStep.hasStatistic` method determines whether a statistic
exists.

The Build method :py:meth:`~buildbot.process.build.Build.getSummaryStatistic` can be used to
aggregate over all steps in a Build.

BuildStep URLs
~~~~~~~~~~~~~~

Each BuildStep has a collection of `links`. Each has a name and a target URL. The web display
displays clickable links for each link, making them a useful way to point to extra information
about a step. For example, a step that uploads a build result to an external service might include
a link to the uploaded file.

To set one of these links, the :class:`BuildStep` should call the
:meth:`~buildbot.process.buildstep.BuildStep.addURL` method with the name of the link and the
target URL. Multiple URLs can be set. For example:

.. code-block:: python

    @defer.inlineCallbacks
    def run(self):
        ... # create and upload report to coverage server
        url = 'http://coverage.example.com/reports/%s' % reportname
        yield self.addURL('coverage', url)

This also works from log observers, which is helpful for instance if the build output points to an
external page such as a detailed log file. The following example parses output of *poudriere*, a
tool for building packages on the FreeBSD operating system.

Example output:

.. code-block:: none

    [00:00:00] Creating the reference jail... done
    ...
    [00:00:01] Logs: /usr/local/poudriere/data/logs/bulk/103amd64-2018Q4/2018-10-03_05h47m30s
    ...
    ... build log without details (those are in the above logs directory) ...

Log observer implementation:

.. code-block:: python

    c = BuildmasterConfig = {}
    c['titleURL'] = 'https://my-buildbot.example.com/'
    # ...
    class PoudriereLogLinkObserver(util.LogLineObserver):
        _regex = re.compile(
            r'Logs: /usr/local/poudriere/data/logs/bulk/([-_/0-9A-Za-z]+)$')

        def __init__(self):
            super().__init__()
            self._finished = False

        def outLineReceived(self, line):
            # Short-circuit if URL already found
            if self._finished:
                return

            m = self._regex.search(line.rstrip())
            if m:
                self._finished = True
                # Let's assume local directory /usr/local/poudriere/data/logs/bulk
                # is available as https://my-buildbot.example.com/poudriere/logs
                poudriere_ui_url = c['titleURL'] + 'poudriere/logs/' + m.group(1)
                # Add URLs for build overview page and for per-package log files
                self.step.addURL('Poudriere build web interface', poudriere_ui_url)
                self.step.addURL('Poudriere logs', poudriere_ui_url + '/logs/')

Discovering files
~~~~~~~~~~~~~~~~~

When implementing a :class:`BuildStep` it may be necessary to know about files that are created
during the build. There are a few worker commands that can be used to find files on the worker and
test for the existence (and type) of files and directories.

The worker provides the following file-discovery related commands:

* `stat` calls :func:`os.stat` for a file in the worker's build directory.
  This can be used to check if a known file exists and whether it is a regular file, directory or symbolic link.

* `listdir` calls :func:`os.listdir` for a directory on the worker.
  It can be used to obtain a list of files that are present in a directory on the worker.

* `glob` calls :func:`glob.glob` on the worker, with a given shell-style pattern containing wildcards.

For example, we could use stat to check if a given path exists and contains ``*.pyc`` files. If the
path does not exist (or anything fails) we mark the step as failed; if the path exists but is not a
directory, we mark the step as having "warnings".

.. code-block:: python


    from buildbot.plugins import steps, util
    from buildbot.process import remotecommand
    from buildbot.interfaces import WorkerSetupError
    import stat

    class MyBuildStep(steps.BuildStep):

        def __init__(self, dirname, **kwargs):
            super().__init__(**kwargs)
            self.dirname = dirname

        @defer.inlineCallbacks
        def run(self):
            # make sure the worker knows about stat
            workerver = (self.workerVersion('stat'),
                        self.workerVersion('glob'))
            if not all(workerver):
                raise WorkerSetupError('need stat and glob')

            cmd = remotecommand.RemoteCommand('stat', {'file': self.dirname})

            yield self.runCommand(cmd)

            if cmd.didFail():
                self.description = ["File not found."]
                return util.FAILURE

            s = cmd.updates["stat"][-1]
            if not stat.S_ISDIR(s[stat.ST_MODE]):
                self.description = ["'tis not a directory"]
                return util.WARNINGS

            cmd = remotecommand.RemoteCommand('glob', {'path': self.dirname + '/*.pyc'})

            yield self.runCommand(cmd)

            if cmd.didFail():
                self.description = ["Glob failed."]
                return util.FAILURE

            files = cmd.updates["files"][-1]
            if len(files):
                self.description = ["Found pycs"] + files
            else:
                self.description = ["No pycs found"]
            return util.SUCCESS


For more information on the available commands, see :doc:`../../developer/master-worker`.

.. todo::

    Step Progress
    BuildStepFailed
