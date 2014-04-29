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


import inspect
import re

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS
from buildbot.util import flatten
from twisted.python import failure
from twisted.python import log
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version
from twisted.spread import pb

# for existing configurations that import WithProperties from here.  We like
# to move this class around just to keep our readers guessing.
from buildbot.process.properties import WithProperties
_hush_pyflakes = [WithProperties]
del _hush_pyflakes


class ShellCommand(buildstep.LoggingBuildStep):

    """I run a single shell command on the buildslave. I return FAILURE if
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
        'slaveEnvironment', 'remote_kwargs', 'command',
        'description', 'descriptionDone', 'descriptionSuffix',
        'haltOnFailure', 'flunkOnFailure']

    command = None  # set this to a command, or set in kwargs
    # logfiles={} # you can also set 'logfiles' to a dictionary, and it
    #               will be merged with any logfiles= argument passed in
    #               to __init__

    # override this on a specific ShellCommand if you want to let it fail
    # without dooming the entire build to a status of FAILURE
    flunkOnFailure = True

    def __init__(self, workdir=None,
                 description=None, descriptionDone=None, descriptionSuffix=None,
                 command=None,
                 usePTY="slave-config",
                 **kwargs):
        # most of our arguments get passed through to the RemoteShellCommand
        # that we create, but first strip out the ones that we pass to
        # BuildStep (like haltOnFailure and friends), and a couple that we
        # consume ourselves.

        if description:
            self.description = description
        if isinstance(self.description, str):
            self.description = [self.description]
        if descriptionDone:
            self.descriptionDone = descriptionDone
        if isinstance(self.descriptionDone, str):
            self.descriptionDone = [self.descriptionDone]

        if descriptionSuffix:
            self.descriptionSuffix = descriptionSuffix
        if isinstance(self.descriptionSuffix, str):
            self.descriptionSuffix = [self.descriptionSuffix]

        if command:
            self.setCommand(command)

        # pull out the ones that LoggingBuildStep wants, then upcall
        buildstep_kwargs = {}
        for k in kwargs.keys()[:]:
            if k in self.__class__.parms:
                buildstep_kwargs[k] = kwargs[k]
                del kwargs[k]
        buildstep.LoggingBuildStep.__init__(self, **buildstep_kwargs)

        # check validity of arguments being passed to RemoteShellCommand
        invalid_args = []
        valid_rsc_args = inspect.getargspec(buildstep.RemoteShellCommand.__init__)[0]
        for arg in kwargs.keys():
            if arg not in valid_rsc_args:
                invalid_args.append(arg)
        # Raise Configuration error in case invalid arguments are present
        if invalid_args:
            config.error("Invalid argument(s) passed to RemoteShellCommand: "
                         + ', '.join(invalid_args))

        # everything left over goes to the RemoteShellCommand
        kwargs['workdir'] = workdir  # including a copy of 'workdir'
        kwargs['usePTY'] = usePTY
        self.remote_kwargs = kwargs

    def setBuild(self, build):
        buildstep.LoggingBuildStep.setBuild(self, build)
        # Set this here, so it gets rendered when we start the step
        self.slaveEnvironment = self.build.slaveEnvironment

    def setStepStatus(self, step_status):
        buildstep.LoggingBuildStep.setStepStatus(self, step_status)

    def setDefaultWorkdir(self, workdir):
        rkw = self.remote_kwargs
        rkw['workdir'] = rkw['workdir'] or workdir

    def getWorkdir(self):
        """
        Get the current notion of the workdir.  Note that this may change
        between instantiation of the step and C{start}, as it is based on the
        build's default workdir, and may even be C{None} before that point.
        """
        return self.remote_kwargs['workdir']

    def setCommand(self, command):
        self.command = command

    def _describe(self, done=False):
        """Return a list of short strings to describe this step, for the
        status display. This uses the first few words of the shell command.
        You can replace this by setting .description in your subclass, or by
        overriding this method to describe the step better.

        @type  done: boolean
        @param done: whether the command is complete or not, to improve the
                     way the command is described. C{done=False} is used
                     while the command is still running, so a single
                     imperfect-tense verb is appropriate ('compiling',
                     'testing', ...) C{done=True} is used when the command
                     has finished, and the default getText() method adds some
                     text, so a simple noun is appropriate ('compile',
                     'tests' ...)
        """

        try:
            if done and self.descriptionDone is not None:
                return self.descriptionDone
            if self.description is not None:
                return self.description

            # we may have no command if this is a step that sets its command
            # name late in the game (e.g., in start())
            if not self.command:
                return ["???"]

            words = self.command
            if isinstance(words, (str, unicode)):
                words = words.split()

            try:
                len(words)
            except (AttributeError, TypeError):
                # WithProperties and Property don't have __len__
                # For old-style classes instances AttributeError raised,
                # for new-style classes instances - TypeError.
                return ["???"]

            # flatten any nested lists
            words = flatten(words, (list, tuple))

            # strip instances and other detritus (which can happen if a
            # description is requested before rendering)
            words = [w for w in words if isinstance(w, (str, unicode))]

            if len(words) < 1:
                return ["???"]
            if len(words) == 1:
                return ["'%s'" % words[0]]
            if len(words) == 2:
                return ["'%s" % words[0], "%s'" % words[1]]
            return ["'%s" % words[0], "%s" % words[1], "...'"]

        except:
            log.err(failure.Failure(), "Error describing step")
            return ["???"]

    def setupEnvironment(self, cmd):
        # merge in anything from Build.slaveEnvironment
        # This can be set from a Builder-level environment, or from earlier
        # BuildSteps. The latter method is deprecated and superseded by
        # BuildProperties.
        # Environment variables passed in by a BuildStep override
        # those passed in at the Builder level.
        slaveEnv = self.slaveEnvironment
        if slaveEnv:
            if cmd.args['env'] is None:
                cmd.args['env'] = {}
            fullSlaveEnv = slaveEnv.copy()
            fullSlaveEnv.update(cmd.args['env'])
            cmd.args['env'] = fullSlaveEnv
            # note that each RemoteShellCommand gets its own copy of the
            # dictionary, so we shouldn't be affecting anyone but ourselves.

    def buildCommandKwargs(self, warnings):
        kwargs = buildstep.LoggingBuildStep.buildCommandKwargs(self)
        kwargs.update(self.remote_kwargs)

        kwargs['command'] = flatten(self.command, (list, tuple))

        # check for the usePTY flag
        if 'usePTY' in kwargs and kwargs['usePTY'] != 'slave-config':
            if self.slaveVersionIsOlderThan("svn", "2.7"):
                warnings.append("NOTE: slave does not allow master to override usePTY\n")
                del kwargs['usePTY']

        # check for the interruptSignal flag
        if "interruptSignal" in kwargs and self.slaveVersionIsOlderThan("shell", "2.15"):
            warnings.append("NOTE: slave does not allow master to specify interruptSignal\n")
            del kwargs['interruptSignal']

        return kwargs

    def start(self):
        # this block is specific to ShellCommands. subclasses that don't need
        # to set up an argv array, an environment, or extra logfiles= (like
        # the Source subclasses) can just skip straight to startCommand()

        warnings = []

        # create the actual RemoteShellCommand instance now
        kwargs = self.buildCommandKwargs(warnings)
        cmd = buildstep.RemoteShellCommand(**kwargs)
        self.setupEnvironment(cmd)

        self.startCommand(cmd, warnings)


class TreeSize(ShellCommand):
    name = "treesize"
    command = ["du", "-s", "-k", "."]
    description = "measuring tree size"
    descriptionDone = "tree size measured"
    kib = None

    def commandComplete(self, cmd):
        out = cmd.logs['stdio'].getText()
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

    def getText(self, cmd, results):
        if self.kib is not None:
            return ["treesize", "%d KiB" % self.kib]
        return ["treesize", "unknown"]


class SetPropertyFromCommand(ShellCommand):
    name = "setproperty"
    renderables = ['property']

    def __init__(self, property=None, extract_fn=None, strip=True, **kwargs):
        self.property = property
        self.extract_fn = extract_fn
        self.strip = strip

        if not ((property is not None) ^ (extract_fn is not None)):
            config.error(
                "Exactly one of property and extract_fn must be set")

        ShellCommand.__init__(self, **kwargs)

        if self.extract_fn:
            self.observer = logobserver.BufferLogObserver(wantStdout=True,
                                                          wantStderr=True)
            self.addLogObserver('stdio', self.observer)

        self.property_changes = {}

    def commandComplete(self, cmd):
        if self.property:
            if cmd.didFail():
                return
            result = cmd.logs['stdio'].getText()
            if self.strip:
                result = result.strip()
            propname = self.property
            self.setProperty(propname, result, "SetPropertyFromCommand Step")
            self.property_changes[propname] = result
        else:
            new_props = self.extract_fn(cmd.rc,
                                        self.observer.getStdout(),
                                        self.observer.getStderr())
            for k, v in new_props.items():
                self.setProperty(k, v, "SetPropertyFromCommand Step")
            self.property_changes = new_props

    def createSummary(self, log):
        if self.property_changes:
            props_set = ["%s: %r" % (k, v)
                         for k, v in self.property_changes.items()]
            self.addCompleteLog('property changes', "\n".join(props_set))

    def getText(self, cmd, results):
        if len(self.property_changes) > 1:
            return ["%d properties set" % len(self.property_changes)]
        elif len(self.property_changes) == 1:
            return ["property '%s' set" % self.property_changes.keys()[0]]
        else:
            # let ShellCommand describe
            return ShellCommand.getText(self, cmd, results)


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


class StringFileWriter(pb.Referenceable):

    """
    FileWriter class that just puts received data into a buffer.

    Used to upload a file from slave for inline processing rather than
    writing into a file on master.
    """

    def __init__(self):
        self.buffer = ""

    def remote_write(self, data):
        self.buffer += data

    def remote_close(self):
        pass


class WarningCountingShellCommand(ShellCommand):
    renderables = ['suppressionFile']

    warnCount = 0
    warningPattern = '.*warning[: ].*'
    # The defaults work for GNU Make.
    directoryEnterPattern = (u"make.*: Entering directory "
                             u"[\u2019\"`'](.*)[\u2019'`\"]")
    directoryLeavePattern = "make.*: Leaving directory"
    suppressionFile = None

    commentEmptyLineRe = re.compile(r"^\s*(\#.*)?$")
    suppressionLineRe = re.compile(r"^\s*(.+?)\s*:\s*(.+?)\s*(?:[:]\s*([0-9]+)(?:-([0-9]+))?\s*)?$")

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

        self.suppressions = []
        self.directoryStack = []

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
            if fileRe is not None and isinstance(fileRe, basestring):
                fileRe = re.compile(fileRe)
            if warnRe is not None and isinstance(warnRe, basestring):
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

        self.myFileWriter = StringFileWriter()

        args = {
            'slavesrc': self.suppressionFile,
            'workdir': self.getWorkdir(),
            'writer': self.myFileWriter,
            'maxsize': None,
            'blocksize': 32 * 1024,
        }
        cmd = buildstep.RemoteCommand('uploadFile', args, ignore_updates=True)
        d = self.runCommand(cmd)
        d.addCallback(self.uploadDone)
        d.addErrback(self.failed)

    def uploadDone(self, dummy):
        lines = self.myFileWriter.buffer.split("\n")
        del(self.myFileWriter)

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

        self.warnCount = 0

        # Now compile a regular expression from whichever warning pattern we're
        # using
        wre = self.warningPattern
        if isinstance(wre, str):
            wre = re.compile(wre)

        directoryEnterRe = self.directoryEnterPattern
        if (directoryEnterRe is not None
                and isinstance(directoryEnterRe, basestring)):
            directoryEnterRe = re.compile(directoryEnterRe)

        directoryLeaveRe = self.directoryLeavePattern
        if (directoryLeaveRe is not None
                and isinstance(directoryLeaveRe, basestring)):
            directoryLeaveRe = re.compile(directoryLeaveRe)

        # Check if each line in the output from this command matched our
        # warnings regular expressions. If did, bump the warnings count and
        # add the line to the collection of lines with warnings
        warnings = []
        # TODO: use log.readlines(), except we need to decide about stdout vs
        # stderr
        for line in log.getText().split("\n"):
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
                self.maybeAddWarning(warnings, line, match)

        # If there were any warnings, make the log if lines with warnings
        # available
        if self.warnCount:
            self.addCompleteLog("warnings (%d)" % self.warnCount,
                                "\n".join(warnings) + "\n")

        warnings_stat = self.step_status.getStatistic('warnings', 0)
        self.step_status.setStatistic('warnings', warnings_stat + self.warnCount)

        old_count = self.getProperty("warnings-count", 0)
        self.setProperty("warnings-count", old_count + self.warnCount, "WarningCountingShellCommand")

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
        total += self.step_status.getStatistic('tests-total', 0)
        self.step_status.setStatistic('tests-total', total)
        failed += self.step_status.getStatistic('tests-failed', 0)
        self.step_status.setStatistic('tests-failed', failed)
        warnings += self.step_status.getStatistic('tests-warnings', 0)
        self.step_status.setStatistic('tests-warnings', warnings)
        passed += self.step_status.getStatistic('tests-passed', 0)
        self.step_status.setStatistic('tests-passed', passed)

    def describe(self, done=False):
        description = WarningCountingShellCommand.describe(self, done)
        if done:
            description = description[:]  # make a private copy
            if self.step_status.hasStatistic('tests-total'):
                total = self.step_status.getStatistic("tests-total", 0)
                failed = self.step_status.getStatistic("tests-failed", 0)
                passed = self.step_status.getStatistic("tests-passed", 0)
                warnings = self.step_status.getStatistic("tests-warnings", 0)
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


class PerlModuleTest(Test):
    command = ["prove", "--lib", "lib", "-r", "t"]
    total = 0

    def evaluateCommand(self, cmd):
        # Get stdio, stripping pesky newlines etc.
        lines = map(
            lambda line: line.replace('\r\n', '').replace('\r', '').replace('\n', ''),
            self.getLog('stdio').readlines()
        )

        total = 0
        passed = 0
        failed = 0
        rc = SUCCESS
        if cmd.didFail():
            rc = FAILURE

        # New version of Test::Harness?
        if "Test Summary Report" in lines:
            test_summary_report_index = lines.index("Test Summary Report")
            del lines[0:test_summary_report_index + 2]

            re_test_result = re.compile(r"^Result: (PASS|FAIL)$|Tests: \d+ Failed: (\d+)\)|Files=\d+, Tests=(\d+)")

            mos = map(lambda line: re_test_result.search(line), lines)
            test_result_lines = [mo.groups() for mo in mos if mo]

            for line in test_result_lines:
                if line[0] == 'FAIL':
                    rc = FAILURE

                if line[1]:
                    failed += int(line[1])
                if line[2]:
                    total = int(line[2])

        else:  # Nope, it's the old version
            re_test_result = re.compile(r"^(All tests successful)|(\d+)/(\d+) subtests failed|Files=\d+, Tests=(\d+),")

            mos = map(lambda line: re_test_result.search(line), lines)
            test_result_lines = [mo.groups() for mo in mos if mo]

            if test_result_lines:
                test_result_line = test_result_lines[0]

                success = test_result_line[0]

                if success:
                    failed = 0

                    test_totals_line = test_result_lines[1]
                    total_str = test_totals_line[3]
                else:
                    failed_str = test_result_line[1]
                    failed = int(failed_str)

                    total_str = test_result_line[2]

                    rc = FAILURE

                total = int(total_str)

        warnings = 0
        if self.warningPattern:
            wre = self.warningPattern
            if isinstance(wre, str):
                wre = re.compile(wre)

            warnings = len([l for l in lines if wre.search(l)])

            # Because there are two paths that are used to determine
            # the success/fail result, I have to modify it here if
            # there were warnings.
            if rc == SUCCESS and warnings:
                rc = WARNINGS

        if total:
            passed = total - failed

            self.setTestResults(total=total, failed=failed, passed=passed,
                                warnings=warnings)

        return rc
