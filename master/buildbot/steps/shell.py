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
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver
# for existing configurations that import WithProperties from here.  We like
# to move this class around just to keep our readers guessing.
from buildbot.process.properties import WithProperties
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.process.results import worst_status
from buildbot.steps.worker import CompositeStepMixin
from buildbot.util import join_list

_hush_pyflakes = [
    WithProperties,
]
del _hush_pyflakes


class TreeSize(buildstep.ShellMixin, buildstep.BuildStep):
    name = "treesize"
    command = ["du", "-s", "-k", "."]
    description = ["measuring", "tree", "size"]

    def __init__(self, **kwargs):
        kwargs = self.setupShellMixin(kwargs)
        super().__init__(**kwargs)
        self.observer = logobserver.BufferLogObserver(wantStdout=True,
                                                      wantStderr=True)
        self.addLogObserver('stdio', self.observer)

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()

        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        out = self.observer.getStdout()
        m = re.search(r'^(\d+)', out)

        kib = None
        if m:
            kib = int(m.group(1))
            self.setProperty("tree-size-KiB", kib, "treesize")
            self.descriptionDone = "treesize {} KiB".format(kib)
        else:
            self.descriptionDone = "treesize unknown"

        if cmd.didFail():
            return FAILURE
        if kib is None:
            return WARNINGS  # not sure how 'du' could fail, but whatever
        return SUCCESS


class SetPropertyFromCommand(buildstep.ShellMixin, buildstep.BuildStep):
    name = "setproperty"
    renderables = ['property']

    def __init__(self, property=None, extract_fn=None, strip=True,
                 includeStdout=True, includeStderr=False, **kwargs):

        kwargs = self.setupShellMixin(kwargs)

        self.property = property
        self.extract_fn = extract_fn
        self.strip = strip
        self.includeStdout = includeStdout
        self.includeStderr = includeStderr

        if not ((property is not None) ^ (extract_fn is not None)):
            config.error(
                "Exactly one of property and extract_fn must be set")

        super().__init__(**kwargs)

        if self.extract_fn:
            self.includeStderr = True

        self.observer = logobserver.BufferLogObserver(
            wantStdout=self.includeStdout,
            wantStderr=self.includeStderr)
        self.addLogObserver('stdio', self.observer)

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()

        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        property_changes = {}

        if self.property:
            if cmd.didFail():
                return FAILURE
            result = self.observer.getStdout()
            if self.strip:
                result = result.strip()
            propname = self.property
            self.setProperty(propname, result, "SetPropertyFromCommand Step")
            property_changes[propname] = result
        else:
            new_props = self.extract_fn(cmd.rc,
                                        self.observer.getStdout(),
                                        self.observer.getStderr())
            for k, v in new_props.items():
                self.setProperty(k, v, "SetPropertyFromCommand Step")
            property_changes = new_props

        props_set = ["{}: {}".format(k, repr(v))
                     for k, v in sorted(property_changes.items())]
        yield self.addCompleteLog('property changes', "\n".join(props_set))

        if len(property_changes) > 1:
            self.descriptionDone = '{} properties set'.format(len(property_changes))
        elif len(property_changes) == 1:
            self.descriptionDone = 'property \'{}\' set'.format(list(property_changes)[0])
        if cmd.didFail():
            return FAILURE
        return SUCCESS


SetPropertyFromCommandNewStyle = SetPropertyFromCommand
deprecatedModuleAttribute(
    Version("buildbot", 3, 0, 0),
    message="Use SetPropertyFromCommand instead. This step will be removed in Buildbot 3.2.",
    moduleName="buildbot.steps.shell",
    name="SetPropertyFromCommandNewStyle",
)


SetProperty = SetPropertyFromCommand
deprecatedModuleAttribute(Version("Buildbot", 0, 8, 8),
                          "It has been renamed to SetPropertyFromCommand",
                          "buildbot.steps.shell", "SetProperty")


class ShellCommand(buildstep.ShellMixin, buildstep.BuildStep):
    name = 'shell'

    def __init__(self, **kwargs):

        if self.__class__ is ShellCommand:
            if 'command' not in kwargs:
                config.error("ShellCommand's `command' argument is not specified")

            # check validity of arguments being passed to RemoteShellCommand
            valid_rsc_args = [
                'command',
                'env',
                'want_stdout',
                'want_stderr',
                'timeout',
                'maxTime',
                'sigtermTime',
                'logfiles',
                'usePTY',
                'logEnviron',
                'collectStdout',
                'collectStderr',
                'interruptSignal',
                'initialStdin',
                'decodeRC',
                'stdioLogName',
                'workdir',
            ] + buildstep.BuildStep.parms

            invalid_args = []
            for arg in kwargs:
                if arg not in valid_rsc_args:
                    invalid_args.append(arg)

            if invalid_args:
                config.error("Invalid argument(s) passed to ShellCommand: " +
                             ', '.join(invalid_args))

        kwargs = self.setupShellMixin(kwargs)
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)
        return cmd.results()


ShellCommandNewStyle = ShellCommand
deprecatedModuleAttribute(
    Version("buildbot", 3, 0, 0),
    message="Use ShellCommand instead. This step will be removed in Buildbot 3.2.",
    moduleName="buildbot.steps.shell",
    name="ShellCommandNewStyle",
)


class Configure(ShellCommand):
    name = "configure"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = "configuring"
    descriptionDone = "configure"
    command = ["./configure"]


ConfigureNewStyle = Configure
deprecatedModuleAttribute(
    Version("buildbot", 3, 0, 0),
    message="Use Configure instead. This step will be removed in Buildbot 3.2.",
    moduleName="buildbot.steps.shell",
    name="ConfigureNewStyle",
)


class WarningCountingShellCommand(buildstep.ShellMixin, CompositeStepMixin, buildstep.BuildStep):
    renderables = [
        'suppressionFile',
        'suppressionList',
        'warningPattern',
        'directoryEnterPattern',
        'directoryLeavePattern',
        'maxWarnCount',
    ]

    warnCount = 0
    warningPattern = '(?i).*warning[: ].*'
    # The defaults work for GNU Make.
    directoryEnterPattern = ("make.*: Entering directory "
                             "[\u2019\"`'](.*)[\u2019'`\"]")
    directoryLeavePattern = "make.*: Leaving directory"
    suppressionFile = None

    commentEmptyLineRe = re.compile(r"^\s*(#.*)?$")
    suppressionLineRe = re.compile(
        r"^\s*(.+?)\s*:\s*(.+?)\s*(?:[:]\s*([0-9]+)(?:-([0-9]+))?\s*)?$")

    def __init__(self,
                 warningPattern=None, warningExtractor=None, maxWarnCount=None,
                 directoryEnterPattern=None, directoryLeavePattern=None,
                 suppressionFile=None, suppressionList=None, **kwargs):
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
        # self.suppressions is already taken, so use something else
        self.suppressionList = suppressionList
        if warningExtractor:
            self.warningExtractor = warningExtractor
        else:
            self.warningExtractor = WarningCountingShellCommand.warnExtractWholeLine
        self.maxWarnCount = maxWarnCount

        if self.__class__ is WarningCountingShellCommand and not kwargs.get('command'):
            # WarningCountingShellCommand class is directly instantiated.
            # Explicitly check that command is set to prevent runtime error
            # later.
            config.error("WarningCountingShellCommand's 'command' argument is not specified")

        kwargs = self.setupShellMixin(kwargs)
        super().__init__(**kwargs)

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
            if fileRe is not None and isinstance(fileRe, str):
                fileRe = re.compile(fileRe)
            if warnRe is not None and isinstance(warnRe, str):
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
                isinstance(directoryEnterRe, str)):
            directoryEnterRe = re.compile(directoryEnterRe)

        directoryLeaveRe = self.directoryLeavePattern
        if (directoryLeaveRe is not None and
                isinstance(directoryLeaveRe, str)):
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
                    file = "{}/{}".format(currentDirectory, file)

            # Skip adding the warning if any suppression matches.
            for fileRe, warnRe, start, end in self.suppressions:
                if not (file is None or fileRe is None or fileRe.match(file)):
                    continue
                if not (warnRe is None or warnRe.search(text)):
                    continue
                if ((start is not None and end is not None) and
                   not (lineNo is not None and start <= lineNo <= end)):
                    continue
                return

        warnings.append(line)
        self.warnCount += 1

    @defer.inlineCallbacks
    def setup_suppression(self):
        if self.suppressionList is not None:
            self.addSuppression(self.suppressionList)

        if self.suppressionFile is not None:
            data = yield self.getFileContentFromWorker(self.suppressionFile, abandonOnFailure=True)
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

    @defer.inlineCallbacks
    def run(self):
        yield self.setup_suppression()

        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        yield self.finish_logs()
        yield self.createSummary()
        return self.evaluateCommand(cmd)

    @defer.inlineCallbacks
    def finish_logs(self):
        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

    def createSummary(self):
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
        result = cmd.results()
        if (self.maxWarnCount is not None and self.warnCount > self.maxWarnCount):
            result = worst_status(result, FAILURE)
        elif self.warnCount:
            result = worst_status(result, WARNINGS)
        return result


WarningCountingShellCommandNewStyle = WarningCountingShellCommand
deprecatedModuleAttribute(
    Version("buildbot", 3, 0, 0),
    message="Use WarningCountingShellCommand instead. This step will be removed in Buildbot 3.2.",
    moduleName="buildbot.steps.shell",
    name="WarningCountingShellCommandNewStyle",
)


class Compile(WarningCountingShellCommand):

    name = "compile"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["compiling"]
    descriptionDone = ["compile"]
    command = ["make", "all"]


CompileNewStyle = Compile
deprecatedModuleAttribute(
    Version("buildbot", 3, 0, 0),
    message="Use Compile instead. This step will be removed in Buildbot 3.2.",
    moduleName="buildbot.steps.shell",
    name="CompileNewStyle",
)


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

    def getResultSummary(self):
        description = []

        if self.hasStatistic('tests-total'):
            total = self.getStatistic("tests-total", 0)
            failed = self.getStatistic("tests-failed", 0)
            passed = self.getStatistic("tests-passed", 0)
            warnings = self.getStatistic("tests-warnings", 0)
            if not total:
                total = failed + passed + warnings

            if total:
                description += [str(total), 'tests']
            if passed:
                description += [str(passed), 'passed']
            if warnings:
                description += [str(warnings), 'warnings']
            if failed:
                description += [str(failed), 'failed']

            if description:
                summary = join_list(description)
                if self.results != SUCCESS:
                    summary += ' ({})'.format(Results[self.results])
                return {'step': summary}

        return super().getResultSummary()


TestNewStyle = Test
deprecatedModuleAttribute(
    Version("buildbot", 3, 0, 0),
    message="Use Test instead. This step will be removed in Buildbot 3.2.",
    moduleName="buildbot.steps.shell",
    name="TestNewStyle",
)


class PerlModuleTestObserver(logobserver.LogLineObserver):

    def __init__(self, warningPattern):
        super().__init__()
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
        super().__init__(*args, **kwargs)
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
