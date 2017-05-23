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
from future.utils import string_types

import inspect
import re

from twisted.python import failure
from twisted.python import log
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.process import remotecommand
# for existing configurations that import WithProperties from here.  We like
# to move this class around just to keep our readers guessing.
from buildbot.process.properties import WithProperties
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.steps.worker import CompositeStepMixin
from buildbot.util import command_to_string
from buildbot.util import flatten
from buildbot.util import join_list

_hush_pyflakes = [WithProperties]
del _hush_pyflakes


class ShellCommand(buildstep.LoggingBuildStep):

    """I run a single shell command on the worker. I return FAILURE if
    the exit code of that command is non-zero, SUCCESS otherwise. To change
    this behavior, override my .evaluateCommand method, or customize
    decodeRC argument

    By default, a failure of this step will mark the whole build as FAILURE.
    To override this, give me an argument of flunkOnFailure=False .

    I create a single Log named 'log' which contains the output of the
    command. To create additional summary Logs, override my .createSummary
    method.

    The shell command I run (a list of argv strings) can be provided in
    several ways:
      - a class-level .command attribute
      - a command= parameter to my constructor (overrides .command)
      - set explicitly with my .setCommand() method (overrides both)

    @ivar command: a list of renderable objects (typically strings or
                   WithProperties instances). This will be used by start()
                   to create a RemoteShellCommand instance.

    @ivar logfiles: a dict mapping log NAMEs to workdir-relative FILENAMEs
                    of their corresponding logfiles. The contents of the file
                    named FILENAME will be put into a LogFile named NAME, ina
                    something approximating real-time. (note that logfiles=
                    is actually handled by our parent class LoggingBuildStep)

    @ivar lazylogfiles: Defaults to False. If True, logfiles will be tracked
                        `lazily', meaning they will only be added when and if
                        they are written to. Empty or nonexistent logfiles
                        will be omitted. (Also handled by class
                        LoggingBuildStep.)
    """

    name = "shell"
    renderables = [
        'command',
        'flunkOnFailure',
        'haltOnFailure',
        'remote_kwargs',
        'workerEnvironment'
    ]

    command = None  # set this to a command, or set in kwargs
    # logfiles={} # you can also set 'logfiles' to a dictionary, and it
    #               will be merged with any logfiles= argument passed in
    #               to __init__

    # override this on a specific ShellCommand if you want to let it fail
    # without dooming the entire build to a status of FAILURE
    flunkOnFailure = True

    def __init__(self, workdir=None,
                 command=None,
                 usePTY=None,
                 **kwargs):
        # most of our arguments get passed through to the RemoteShellCommand
        # that we create, but first strip out the ones that we pass to
        # BuildStep (like haltOnFailure and friends), and a couple that we
        # consume ourselves.

        if command:
            self.setCommand(command)

        if self.__class__ is ShellCommand and not command:
            # ShellCommand class is directly instantiated.
            # Explicitly check that command is set to prevent runtime error
            # later.
            config.error("ShellCommand's `command' argument is not specified")

        # pull out the ones that LoggingBuildStep wants, then upcall
        buildstep_kwargs = {}
        # workdir is here first positional argument, but it belongs to
        # BuildStep parent
        kwargs['workdir'] = workdir
        for k in list(kwargs):
            if k in self.__class__.parms:
                buildstep_kwargs[k] = kwargs[k]
                del kwargs[k]
        buildstep.LoggingBuildStep.__init__(self, **buildstep_kwargs)

        # check validity of arguments being passed to RemoteShellCommand
        invalid_args = []
        if PY3:
            signature = inspect.signature(
                remotecommand.RemoteShellCommand.__init__)
            valid_rsc_args = signature.parameters.keys()
        else:
            valid_rsc_args = inspect.getargspec(
                remotecommand.RemoteShellCommand.__init__)[0]
        for arg in kwargs:
            if arg not in valid_rsc_args:
                invalid_args.append(arg)
        # Raise Configuration error in case invalid arguments are present
        if invalid_args:
            config.error("Invalid argument(s) passed to RemoteShellCommand: " +
                         ', '.join(invalid_args))

        # everything left over goes to the RemoteShellCommand
        kwargs['usePTY'] = usePTY
        self.remote_kwargs = kwargs
        self.remote_kwargs['workdir'] = workdir

    def setBuild(self, build):
        buildstep.LoggingBuildStep.setBuild(self, build)
        # Set this here, so it gets rendered when we start the step
        self.workerEnvironment = self.build.workerEnvironment

    def setCommand(self, command):
        self.command = command

    def _describe(self, done=False):
        return None

    def describe(self, done=False):
        if self.stopped and not self.rendered:
            return u"stopped early"
        assert(self.rendered)
        desc = self._describe(done)
        if not desc:
            return None
        if self.descriptionSuffix:
            desc = desc + u' ' + join_list(self.descriptionSuffix)
        return desc

    def getCurrentSummary(self):
        cmdsummary = self._getLegacySummary(False)
        if cmdsummary:
            return {u'step': cmdsummary}
        return super(ShellCommand, self).getCurrentSummary()

    def getResultSummary(self):
        cmdsummary = self._getLegacySummary(True)

        if cmdsummary:
            if self.results != SUCCESS:
                cmdsummary += u' (%s)' % Results[self.results]
            return {u'step': cmdsummary}

        return super(ShellCommand, self).getResultSummary()

    def _getLegacySummary(self, done):
        # defer to the describe method, if set
        description = self.describe(done)
        if description:
            return join_list(description)

        # defer to descriptions, if they're set
        if (not done and self.description) or (done and self.descriptionDone):
            return None

        try:
            # if self.cmd is set, then use the RemoteCommand's info
            if self.cmd:
                command = self.cmd.remote_command
            # otherwise, if we were configured with a command, use that
            elif self.command:
                command = self.command
            else:
                return None

            rv = command_to_string(command)

            # add the descriptionSuffix, if one was given
            if self.descriptionSuffix:
                rv = rv + u' ' + join_list(self.descriptionSuffix)

            return rv

        except Exception:
            log.err(failure.Failure(), "Error describing step")
            return None

    def setupEnvironment(self, cmd):
        # merge in anything from workerEnvironment (which comes from the builder
        # config) Environment variables passed in by a BuildStep override those
        # passed in at the Builder level, so if we have any from the builder,
        # apply those and then update with the args from the buildstep
        # (cmd.args)
        workerEnv = self.workerEnvironment
        if workerEnv:
            if cmd.args['env'] is None:
                cmd.args['env'] = {}
            fullWorkerEnv = workerEnv.copy()
            fullWorkerEnv.update(cmd.args['env'])
            cmd.args['env'] = fullWorkerEnv
            # note that each RemoteShellCommand gets its own copy of the
            # dictionary, so we shouldn't be affecting anyone but ourselves.

    def buildCommandKwargs(self, warnings):
        kwargs = buildstep.LoggingBuildStep.buildCommandKwargs(self)
        kwargs.update(self.remote_kwargs)
        kwargs['workdir'] = self.workdir

        kwargs['command'] = flatten(self.command, (list, tuple))

        # check for the usePTY flag
        if 'usePTY' in kwargs and kwargs['usePTY'] is not None:
            if self.workerVersionIsOlderThan("shell", "2.7"):
                warnings.append(
                    "NOTE: worker does not allow master to override usePTY\n")
                del kwargs['usePTY']

        # check for the interruptSignal flag
        if "interruptSignal" in kwargs and self.workerVersionIsOlderThan("shell", "2.15"):
            warnings.append(
                "NOTE: worker does not allow master to specify interruptSignal\n")
            del kwargs['interruptSignal']

        return kwargs

    def start(self):
        # this block is specific to ShellCommands. subclasses that don't need
        # to set up an argv array, an environment, or extra logfiles= (like
        # the Source subclasses) can just skip straight to startCommand()

        warnings = []

        # create the actual RemoteShellCommand instance now
        kwargs = self.buildCommandKwargs(warnings)
        cmd = remotecommand.RemoteShellCommand(**kwargs)
        self.setupEnvironment(cmd)

        self.startCommand(cmd, warnings)


class TreeSize(ShellCommand):
    name = "treesize"
    command = ["du", "-s", "-k", "."]
    description = "measuring tree size"
    kib = None

    def __init__(self, **kwargs):
        ShellCommand.__init__(self, **kwargs)
        self.observer = logobserver.BufferLogObserver(wantStdout=True,
                                                      wantStderr=True)
        self.addLogObserver('stdio', self.observer)

    def commandComplete(self, cmd):
        out = self.observer.getStdout()
        m = re.search(r'^(\d+)', out)
        if m:
            self.kib = int(m.group(1))
            self.setProperty("tree-size-KiB", self.kib, "treesize")

    def evaluateCommand(self, cmd):
        if cmd.didFail():
            return FAILURE
        if self.kib is None:
            return WARNINGS  # not sure how 'du' could fail, but whatever
        return SUCCESS

    def _describe(self, done=False):
        if self.kib is not None:
            return ["treesize", "%d KiB" % self.kib]
        return ["treesize", "unknown"]


class SetPropertyFromCommand(ShellCommand):
    name = "setproperty"
    renderables = ['property']

    def __init__(self, property=None, extract_fn=None, strip=True,
                 includeStdout=True, includeStderr=False, **kwargs):
        self.property = property
        self.extract_fn = extract_fn
        self.strip = strip
        self.includeStdout = includeStdout
        self.includeStderr = includeStderr

        if not ((property is not None) ^ (extract_fn is not None)):
            config.error(
                "Exactly one of property and extract_fn must be set")

        ShellCommand.__init__(self, **kwargs)

        if self.extract_fn:
            self.includeStderr = True

        self.observer = logobserver.BufferLogObserver(
            wantStdout=self.includeStdout,
            wantStderr=self.includeStderr)
        self.addLogObserver('stdio', self.observer)

        self.property_changes = {}

    def commandComplete(self, cmd):
        if self.property:
            if cmd.didFail():
                return
            result = self.observer.getStdout()
            if self.strip:
                result = result.strip()
            propname = self.property
            self.setProperty(propname, result, "SetPropertyFromCommand Step")
            self.property_changes[propname] = result
        else:
            new_props = self.extract_fn(cmd.rc,
                                        self.observer.getStdout(),
                                        self.observer.getStderr())
            for k, v in iteritems(new_props):
                self.setProperty(k, v, "SetPropertyFromCommand Step")
            self.property_changes = new_props

    def createSummary(self, log):
        if self.property_changes:
            props_set = ["%s: %r" % (k, v)
                         for k, v in sorted(iteritems(self.property_changes))]
            self.addCompleteLog('property changes', "\n".join(props_set))

    def describe(self, done=False):
        if len(self.property_changes) > 1:
            return ["%d properties set" % len(self.property_changes)]
        elif len(self.property_changes) == 1:
            return ["property '%s' set" % list(self.property_changes)[0]]
        # else:
        # let ShellCommand describe
        return ShellCommand.describe(self, done)


SetProperty = SetPropertyFromCommand
deprecatedModuleAttribute(Version("Buildbot", 0, 8, 8),
                          "It has been renamed to SetPropertyFromCommand",
                          "buildbot.steps.shell", "SetProperty")


class Configure(ShellCommand):

    name = "configure"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["configuring"]
    descriptionDone = ["configure"]
    command = ["./configure"]


class WarningCountingShellCommand(ShellCommand, CompositeStepMixin):
    renderables = ['suppressionFile']

    warnCount = 0
    warningPattern = '(?i).*warning[: ].*'
    # The defaults work for GNU Make.
    directoryEnterPattern = (u"make.*: Entering directory "
                             u"[\u2019\"`'](.*)[\u2019'`\"]")
    directoryLeavePattern = "make.*: Leaving directory"
    suppressionFile = None

    commentEmptyLineRe = re.compile(r"^\s*(#.*)?$")
    suppressionLineRe = re.compile(
        r"^\s*(.+?)\s*:\s*(.+?)\s*(?:[:]\s*([0-9]+)(?:-([0-9]+))?\s*)?$")

    def __init__(self,
                 warningPattern=None, warningExtractor=None, maxWarnCount=None,
                 directoryEnterPattern=None, directoryLeavePattern=None,
                 suppressionFile=None, **kwargs):
        # See if we've been given a regular expression to use to match
        # warnings. If not, use a default that assumes any line with "warning"
        # present is a warning. This may lead to false positives in some cases.
        if warningPattern:
            self.warningPattern = warningPattern
        if directoryEnterPattern:
            self.directoryEnterPattern = directoryEnterPattern
        if directoryLeavePattern:
            self.directoryLeavePattern = directoryLeavePattern
        if suppressionFile:
            self.suppressionFile = suppressionFile
        if warningExtractor:
            self.warningExtractor = warningExtractor
        else:
            self.warningExtractor = WarningCountingShellCommand.warnExtractWholeLine
        self.maxWarnCount = maxWarnCount

        # And upcall to let the base class do its work
        ShellCommand.__init__(self, **kwargs)

        if self.__class__ is WarningCountingShellCommand and \
                not kwargs.get('command'):
            # WarningCountingShellCommand class is directly instantiated.
            # Explicitly check that command is set to prevent runtime error
            # later.
            config.error("WarningCountingShellCommand's `command' argument "
                         "is not specified")

        self.suppressions = []
        self.directoryStack = []

        self.warnCount = 0
        self.loggedWarnings = []

        self.addLogObserver(
            'stdio',
            logobserver.LineConsumerLogObserver(self.warningLogConsumer))

    def addSuppression(self, suppressionList):
        """
        This method can be used to add patters of warnings that should
        not be counted.

        It takes a single argument, a list of patterns.

        Each pattern is a 4-tuple (FILE-RE, WARN-RE, START, END).

        FILE-RE is a regular expression (string or compiled regexp), or None.
        If None, the pattern matches all files, else only files matching the
        regexp. If directoryEnterPattern is specified in the class constructor,
        matching is against the full path name, eg. src/main.c.

        WARN-RE is similarly a regular expression matched against the
        text of the warning, or None to match all warnings.

        START and END form an inclusive line number range to match against. If
        START is None, there is no lower bound, similarly if END is none there
        is no upper bound."""

        for fileRe, warnRe, start, end in suppressionList:
            if fileRe is not None and isinstance(fileRe, string_types):
                fileRe = re.compile(fileRe)
            if warnRe is not None and isinstance(warnRe, string_types):
                warnRe = re.compile(warnRe)
            self.suppressions.append((fileRe, warnRe, start, end))

    def warnExtractWholeLine(self, line, match):
        """
        Extract warning text as the whole line.
        No file names or line numbers."""
        return (None, None, line)

    def warnExtractFromRegexpGroups(self, line, match):
        """
        Extract file name, line number, and warning text as groups (1,2,3)
        of warningPattern match."""
        file = match.group(1)
        lineNo = match.group(2)
        if lineNo is not None:
            lineNo = int(lineNo)
        text = match.group(3)
        return (file, lineNo, text)

    def warningLogConsumer(self):
        # Now compile a regular expression from whichever warning pattern we're
        # using
        wre = self.warningPattern
        if isinstance(wre, str):
            wre = re.compile(wre)

        directoryEnterRe = self.directoryEnterPattern
        if (directoryEnterRe is not None and
                isinstance(directoryEnterRe, string_types)):
            directoryEnterRe = re.compile(directoryEnterRe)

        directoryLeaveRe = self.directoryLeavePattern
        if (directoryLeaveRe is not None and
                isinstance(directoryLeaveRe, string_types)):
            directoryLeaveRe = re.compile(directoryLeaveRe)

        # Check if each line in the output from this command matched our
        # warnings regular expressions. If did, bump the warnings count and
        # add the line to the collection of lines with warnings
        self.loggedWarnings = []
        while True:
            stream, line = yield
            if directoryEnterRe:
                match = directoryEnterRe.search(line)
                if match:
                    self.directoryStack.append(match.group(1))
                    continue
            if (directoryLeaveRe and
                self.directoryStack and
                    directoryLeaveRe.search(line)):
                self.directoryStack.pop()
                continue

            match = wre.match(line)
            if match:
                self.maybeAddWarning(self.loggedWarnings, line, match)

    def maybeAddWarning(self, warnings, line, match):
        if self.suppressions:
            (file, lineNo, text) = self.warningExtractor(self, line, match)
            lineNo = lineNo and int(lineNo)

            if file is not None and file != "" and self.directoryStack:
                currentDirectory = '/'.join(self.directoryStack)
                if currentDirectory is not None and currentDirectory != "":
                    file = "%s/%s" % (currentDirectory, file)

            # Skip adding the warning if any suppression matches.
            for fileRe, warnRe, start, end in self.suppressions:
                if not (file is None or fileRe is None or fileRe.match(file)):
                    continue
                if not (warnRe is None or warnRe.search(text)):
                    continue
                if not ((start is None and end is None) or
                        (lineNo is not None and start <= lineNo and end >= lineNo)):
                    continue
                return

        warnings.append(line)
        self.warnCount += 1

    def start(self):
        if self.suppressionFile is None:
            return ShellCommand.start(self)
        d = self.getFileContentFromWorker(
            self.suppressionFile, abandonOnFailure=True)
        d.addCallback(self.uploadDone)
        d.addErrback(self.failed)

    def uploadDone(self, data):
        lines = data.split("\n")

        list = []
        for line in lines:
            if self.commentEmptyLineRe.match(line):
                continue
            match = self.suppressionLineRe.match(line)
            if (match):
                file, test, start, end = match.groups()
                if (end is not None):
                    end = int(end)
                if (start is not None):
                    start = int(start)
                    if end is None:
                        end = start
                list.append((file, test, start, end))

        self.addSuppression(list)
        return ShellCommand.start(self)

    def createSummary(self, log):
        """
        Match log lines against warningPattern.

        Warnings are collected into another log for this step, and the
        build-wide 'warnings-count' is updated."""

        # If there were any warnings, make the log if lines with warnings
        # available
        if self.warnCount:
            self.addCompleteLog("warnings (%d)" % self.warnCount,
                                "\n".join(self.loggedWarnings) + "\n")

        warnings_stat = self.getStatistic('warnings', 0)
        self.setStatistic('warnings', warnings_stat + self.warnCount)

        old_count = self.getProperty("warnings-count", 0)
        self.setProperty(
            "warnings-count", old_count + self.warnCount, "WarningCountingShellCommand")

    def evaluateCommand(self, cmd):
        if (cmd.didFail() or
                (self.maxWarnCount is not None and self.warnCount > self.maxWarnCount)):
            return FAILURE
        if self.warnCount:
            return WARNINGS
        return SUCCESS


class Compile(WarningCountingShellCommand):

    name = "compile"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["compiling"]
    descriptionDone = ["compile"]
    command = ["make", "all"]


class Test(WarningCountingShellCommand):

    name = "test"
    warnOnFailure = 1
    description = ["testing"]
    descriptionDone = ["test"]
    command = ["make", "test"]

    def setTestResults(self, total=0, failed=0, passed=0, warnings=0):
        """
        Called by subclasses to set the relevant statistics; this actually
        adds to any statistics already present
        """
        total += self.getStatistic('tests-total', 0)
        self.setStatistic('tests-total', total)
        failed += self.getStatistic('tests-failed', 0)
        self.setStatistic('tests-failed', failed)
        warnings += self.getStatistic('tests-warnings', 0)
        self.setStatistic('tests-warnings', warnings)
        passed += self.getStatistic('tests-passed', 0)
        self.setStatistic('tests-passed', passed)

    def describe(self, done=False):
        description = WarningCountingShellCommand.describe(self, done)
        if done:
            if not description:
                description = []
            description = description[:]  # make a private copy
            if self.hasStatistic('tests-total'):
                total = self.getStatistic("tests-total", 0)
                failed = self.getStatistic("tests-failed", 0)
                passed = self.getStatistic("tests-passed", 0)
                warnings = self.getStatistic("tests-warnings", 0)
                if not total:
                    total = failed + passed + warnings

                if total:
                    description.append('%d tests' % total)
                if passed:
                    description.append('%d passed' % passed)
                if warnings:
                    description.append('%d warnings' % warnings)
                if failed:
                    description.append('%d failed' % failed)
        return description


class PerlModuleTestObserver(logobserver.LogLineObserver):

    def __init__(self, warningPattern):
        logobserver.LogLineObserver.__init__(self)
        if warningPattern:
            self.warningPattern = re.compile(warningPattern)
        else:
            self.warningPattern = None
        self.rc = SUCCESS
        self.total = 0
        self.failed = 0
        self.warnings = 0
        self.newStyle = False
        self.complete = False

    failedRe = re.compile(r"Tests: \d+ Failed: (\d+)\)")
    testsRe = re.compile(r"Files=\d+, Tests=(\d+)")
    oldFailureCountsRe = re.compile(r"(\d+)/(\d+) subtests failed")
    oldSuccessCountsRe = re.compile(r"Files=\d+, Tests=(\d+),")

    def outLineReceived(self, line):
        if self.warningPattern.match(line):
            self.warnings += 1
        if self.newStyle:
            if line.startswith('Result: FAIL'):
                self.rc = FAILURE
            mo = self.failedRe.search(line)
            if mo:
                self.failed += int(mo.group(1))
                if self.failed:
                    self.rc = FAILURE
            mo = self.testsRe.search(line)
            if mo:
                self.total = int(mo.group(1))
        else:
            if line.startswith('Test Summary Report'):
                self.newStyle = True
            mo = self.oldFailureCountsRe.search(line)
            if mo:
                self.failed = int(mo.group(1))
                self.total = int(mo.group(2))
                self.rc = FAILURE
            mo = self.oldSuccessCountsRe.search(line)
            if mo:
                self.total = int(mo.group(1))


class PerlModuleTest(Test):
    command = ["prove", "--lib", "lib", "-r", "t"]
    total = 0

    def __init__(self, *args, **kwargs):
        Test.__init__(self, *args, **kwargs)
        self.observer = PerlModuleTestObserver(
            warningPattern=self.warningPattern)
        self.addLogObserver('stdio', self.observer)

    def evaluateCommand(self, cmd):
        if self.observer.total:
            passed = self.observer.total - self.observer.failed

            self.setTestResults(
                total=self.observer.total,
                failed=self.observer.failed,
                passed=passed,
                warnings=self.observer.warnings)

        rc = self.observer.rc
        if rc == SUCCESS and self.observer.warnings:
            rc = WARNINGS
        return rc
