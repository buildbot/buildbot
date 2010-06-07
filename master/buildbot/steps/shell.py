# -*- test-case-name: buildbot.test.test_steps,buildbot.test.test_properties -*-

import re
from twisted.python import log
from twisted.spread import pb
from buildbot.process.buildstep import LoggingBuildStep, RemoteShellCommand
from buildbot.process.buildstep import RemoteCommand
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, STDOUT, STDERR
from buildbot.interfaces import BuildSlaveTooOldError

# for existing configurations that import WithProperties from here.  We like
# to move this class around just to keep our readers guessing.
from buildbot.process.properties import WithProperties
_hush_pyflakes = [WithProperties]
del _hush_pyflakes

class ShellCommand(LoggingBuildStep):
    """I run a single shell command on the buildslave. I return FAILURE if
    the exit code of that command is non-zero, SUCCESS otherwise. To change
    this behavior, override my .evaluateCommand method.

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
    description = None # set this to a list of short strings to override
    descriptionDone = None # alternate description when the step is complete
    command = None # set this to a command, or set in kwargs
    # logfiles={} # you can also set 'logfiles' to a dictionary, and it
    #               will be merged with any logfiles= argument passed in
    #               to __init__

    # override this on a specific ShellCommand if you want to let it fail
    # without dooming the entire build to a status of FAILURE
    flunkOnFailure = True

    def __init__(self, workdir=None,
                 description=None, descriptionDone=None,
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
        if command:
            self.setCommand(command)

        # pull out the ones that LoggingBuildStep wants, then upcall
        buildstep_kwargs = {}
        for k in kwargs.keys()[:]:
            if k in self.__class__.parms:
                buildstep_kwargs[k] = kwargs[k]
                del kwargs[k]
        LoggingBuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(workdir=workdir,
                                 description=description,
                                 descriptionDone=descriptionDone,
                                 command=command)

        # everything left over goes to the RemoteShellCommand
        kwargs['workdir'] = workdir # including a copy of 'workdir'
        kwargs['usePTY'] = usePTY
        self.remote_kwargs = kwargs
        # we need to stash the RemoteShellCommand's args too
        self.addFactoryArguments(**kwargs)

    def setStepStatus(self, step_status):
        LoggingBuildStep.setStepStatus(self, step_status)

    def setDefaultWorkdir(self, workdir):
        rkw = self.remote_kwargs
        rkw['workdir'] = rkw['workdir'] or workdir

    def setCommand(self, command):
        self.command = command

    def describe(self, done=False):
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
                return list(self.descriptionDone)
            if self.description is not None:
                return list(self.description)

            properties = self.build.getProperties()
            words = self.command
            if isinstance(words, (str, unicode)):
                words = words.split()
            # render() each word to handle WithProperties objects
            words = properties.render(words)
            if len(words) < 1:
                return ["???"]
            if len(words) == 1:
                return ["'%s'" % words[0]]
            if len(words) == 2:
                return ["'%s" % words[0], "%s'" % words[1]]
            return ["'%s" % words[0], "%s" % words[1], "...'"]
        except:
            log.msg("Error describing step")
            log.err()
            return ["???"]

    def setupEnvironment(self, cmd):
        # merge in anything from Build.slaveEnvironment
        # This can be set from a Builder-level environment, or from earlier
        # BuildSteps. The latter method is deprecated and superceded by
        # BuildProperties.
        # Environment variables passed in by a BuildStep override
        # those passed in at the Builder level.
        properties = self.build.getProperties()
        slaveEnv = self.build.slaveEnvironment
        if slaveEnv:
            if cmd.args['env'] is None:
                cmd.args['env'] = {}
            fullSlaveEnv = slaveEnv.copy()
            fullSlaveEnv.update(cmd.args['env'])
            cmd.args['env'] = properties.render(fullSlaveEnv)
            # note that each RemoteShellCommand gets its own copy of the
            # dictionary, so we shouldn't be affecting anyone but ourselves.

    def checkForOldSlaveAndLogfiles(self):
        if not self.logfiles:
            return # doesn't matter
        if not self.slaveVersionIsOlderThan("shell", "2.1"):
            return # slave is new enough
        # this buildslave is too old and will ignore the 'logfiles'
        # argument. You'll either have to pull the logfiles manually
        # (say, by using 'cat' in a separate RemoteShellCommand) or
        # upgrade the buildslave.
        msg1 = ("Warning: buildslave %s is too old "
                "to understand logfiles=, ignoring it."
               % self.getSlaveName())
        msg2 = "You will have to pull this logfile (%s) manually."
        log.msg(msg1)
        for logname,remotefilevalue in self.logfiles.items():
            remotefilename = remotefilevalue
            # check for a dictionary of options
            if type(remotefilevalue) == dict:
                remotefilename = remotefilevalue['filename']

            newlog = self.addLog(logname)
            newlog.addHeader(msg1 + "\n")
            newlog.addHeader(msg2 % remotefilename + "\n")
            newlog.finish()
        # now prevent setupLogfiles() from adding them
        self.logfiles = {}

    def start(self):
        # this block is specific to ShellCommands. subclasses that don't need
        # to set up an argv array, an environment, or extra logfiles= (like
        # the Source subclasses) can just skip straight to startCommand()
        properties = self.build.getProperties()

        warnings = []

        # create the actual RemoteShellCommand instance now
        kwargs = properties.render(self.remote_kwargs)
        command = properties.render(self.command)
        kwargs['command'] = command
        kwargs['logfiles'] = self.logfiles

        # check for the usePTY flag
        if kwargs.has_key('usePTY') and kwargs['usePTY'] != 'slave-config':
            if self.slaveVersionIsOlderThan("svn", "2.7"):
                warnings.append("NOTE: slave does not allow master to override usePTY\n")

        cmd = RemoteShellCommand(**kwargs)
        self.setupEnvironment(cmd)
        self.checkForOldSlaveAndLogfiles()

        self.startCommand(cmd, warnings)



class TreeSize(ShellCommand):
    name = "treesize"
    command = ["du", "-s", "-k", "."]
    description = "measuring tree size"
    descriptionDone = "tree size measured"
    kib = None

    def __init__(self, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)

    def commandComplete(self, cmd):
        out = cmd.logs['stdio'].getText()
        m = re.search(r'^(\d+)', out)
        if m:
            self.kib = int(m.group(1))
            self.setProperty("tree-size-KiB", self.kib, "treesize")

    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
            return FAILURE
        if self.kib is None:
            return WARNINGS # not sure how 'du' could fail, but whatever
        return SUCCESS

    def getText(self, cmd, results):
        if self.kib is not None:
            return ["treesize", "%d KiB" % self.kib]
        return ["treesize", "unknown"]

class SetProperty(ShellCommand):
    name = "setproperty"

    def __init__(self, property=None, extract_fn=None, strip=True, **kwargs):
        self.property = property
        self.extract_fn = extract_fn
        self.strip = strip

        assert (property is not None) ^ (extract_fn is not None), \
                "Exactly one of property and extract_fn must be set"

        ShellCommand.__init__(self, **kwargs)

        self.addFactoryArguments(property=self.property)
        self.addFactoryArguments(extract_fn=self.extract_fn)
        self.addFactoryArguments(strip=self.strip)

        self.property_changes = {}

    def commandComplete(self, cmd):
        if self.property:
            result = cmd.logs['stdio'].getText()
            if self.strip: result = result.strip()
            propname = self.build.getProperties().render(self.property)
            self.setProperty(propname, result, "SetProperty Step")
            self.property_changes[propname] = result
        else:
            log = cmd.logs['stdio']
            new_props = self.extract_fn(cmd.rc,
                    ''.join(log.getChunks([STDOUT], onlyText=True)),
                    ''.join(log.getChunks([STDERR], onlyText=True)))
            for k,v in new_props.items():
                self.setProperty(k, v, "SetProperty Step")
            self.property_changes = new_props

    def createSummary(self, log):
        props_set = [ "%s: %r" % (k,v) for k,v in self.property_changes.items() ]
        self.addCompleteLog('property changes', "\n".join(props_set))

    def getText(self, cmd, results):
        if self.property_changes:
            return [ "set props:" ] + self.property_changes.keys()
        else:
            return [ "no change" ]

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

class SilentRemoteCommand(RemoteCommand):
    """
    Remote command subclass used to run an internal file upload command on the
    slave. We do not need any progress updates from such command, so override
    remoteUpdate() with an empty method.
    """
    def remoteUpdate(self, update):
        pass

class WarningCountingShellCommand(ShellCommand):
    warnCount = 0
    warningPattern = '.*warning[: ].*'
    # The defaults work for GNU Make.
    directoryEnterPattern = "make.*: Entering directory [\"`'](.*)['`\"]"
    directoryLeavePattern = "make.*: Leaving directory"
    suppressionFile = None

    commentEmptyLineRe = re.compile(r"^\s*(\#.*)?$")
    suppressionLineRe = re.compile(r"^\s*(.+?)\s*:\s*(.+?)\s*(?:[:]\s*([0-9]+)(?:-([0-9]+))?\s*)?$")

    def __init__(self, workdir=None,
                 warningPattern=None, warningExtractor=None,
                 directoryEnterPattern=None, directoryLeavePattern=None,
                 suppressionFile=None, **kwargs):
        self.workdir = workdir
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

        # And upcall to let the base class do its work
        ShellCommand.__init__(self, workdir=workdir, **kwargs)

        self.addFactoryArguments(warningPattern=warningPattern,
                                 directoryEnterPattern=directoryEnterPattern,
                                 directoryLeavePattern=directoryLeavePattern,
                                 warningExtractor=warningExtractor,
                                 suppressionFile=suppressionFile)
        self.suppressions = []
        self.directoryStack = []

    def setDefaultWorkdir(self, workdir):
        if self.workdir is None:
            self.workdir = workdir
        ShellCommand.setDefaultWorkdir(self, workdir)

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
            if fileRe != None and isinstance(fileRe, str):
                fileRe = re.compile(fileRe)
            if warnRe != None and isinstance(warnRe, str):
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
        if lineNo != None:
            lineNo = int(lineNo)
        text = match.group(3)
        return (file, lineNo, text)

    def maybeAddWarning(self, warnings, line, match):
        if self.suppressions:
            (file, lineNo, text) = self.warningExtractor(self, line, match)

            if file != None and file != "" and self.directoryStack:
                currentDirectory = self.directoryStack[-1]
                if currentDirectory != None and currentDirectory != "":
                    file = "%s/%s" % (currentDirectory, file)

            # Skip adding the warning if any suppression matches.
            for fileRe, warnRe, start, end in self.suppressions:
                if ( (file == None or fileRe == None or fileRe.search(file)) and
                     (warnRe == None or  warnRe.search(text)) and
                     lineNo != None and
                     (start == None or start <= lineNo) and
                     (end == None or end >= lineNo) ):
                    return

        warnings.append(line)
        self.warnCount += 1

    def start(self):
        if self.suppressionFile == None:
            return ShellCommand.start(self)

        version = self.slaveVersion("uploadFile")
        if not version:
            m = "Slave is too old, does not know about uploadFile"
            raise BuildSlaveTooOldError(m)

        self.myFileWriter = StringFileWriter()

        properties = self.build.getProperties()

        args = {
            'slavesrc': properties.render(self.suppressionFile),
            'workdir': self.workdir,
            'writer': self.myFileWriter,
            'maxsize': None,
            'blocksize': 32*1024,
            }
        cmd = SilentRemoteCommand('uploadFile', args)
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
                if (end != None):
                    end = int(end)
                if (start != None):
                    start = int(start)
                    if end == None:
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
        if not self.warningPattern:
            return

        wre = self.warningPattern
        if isinstance(wre, str):
            wre = re.compile(wre)

        directoryEnterRe = self.directoryEnterPattern
        if directoryEnterRe != None and isinstance(directoryEnterRe, str):
            directoryEnterRe = re.compile(directoryEnterRe)

        directoryLeaveRe = self.directoryLeavePattern
        if directoryLeaveRe != None and isinstance(directoryLeaveRe, str):
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
                if (directoryLeaveRe and
                    self.directoryStack and
                    directoryLeaveRe.search(line)):
                        self.directoryStack.pop()

            match = wre.match(line)
            if match:
                self.maybeAddWarning(warnings, line, match)

        # If there were any warnings, make the log if lines with warnings
        # available
        if self.warnCount:
            self.addCompleteLog("warnings", "\n".join(warnings) + "\n")

        warnings_stat = self.step_status.getStatistic('warnings', 0)
        self.step_status.setStatistic('warnings', warnings_stat + self.warnCount)

        try:
            old_count = self.getProperty("warnings-count")
        except KeyError:
            old_count = 0
        self.setProperty("warnings-count", old_count + self.warnCount, "WarningCountingShellCommand")


    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
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

    OFFprogressMetrics = ('output',)
    # things to track: number of files compiled, number of directories
    # traversed (assuming 'make' is being used)

    def createSummary(self, log):
        # TODO: grep for the characteristic GCC error lines and
        # assemble them into a pair of buffers
        WarningCountingShellCommand.createSummary(self, log)

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
    command=["prove", "--lib", "lib", "-r", "t"]
    total = 0

    def evaluateCommand(self, cmd):
        # Get stdio, stripping pesky newlines etc.
        lines = map(
            lambda line : line.replace('\r\n','').replace('\r','').replace('\n',''),
            self.getLog('stdio').readlines()
            )

        total = 0
        passed = 0
        failed = 0
        rc = cmd.rc

        # New version of Test::Harness?
        try:
            test_summary_report_index = lines.index("Test Summary Report")

            del lines[0:test_summary_report_index + 2]

            re_test_result = re.compile("^Result: (PASS|FAIL)$|Tests: \d+ Failed: (\d+)\)|Files=\d+, Tests=(\d+)")

            mos = map(lambda line: re_test_result.search(line), lines)
            test_result_lines = [mo.groups() for mo in mos if mo]

            for line in test_result_lines:
                if line[0] == 'PASS':
                    rc = SUCCESS
                elif line[0] == 'FAIL':
                    rc = FAILURE
                elif line[1]:
                    failed += int(line[1])
                elif line[2]:
                    total = int(line[2])

        except ValueError: # Nope, it's the old version
            re_test_result = re.compile("^(All tests successful)|(\d+)/(\d+) subtests failed|Files=\d+, Tests=(\d+),")

            mos = map(lambda line: re_test_result.search(line), lines)
            test_result_lines = [mo.groups() for mo in mos if mo]

            if test_result_lines:
                test_result_line = test_result_lines[0]

                success = test_result_line[0]

                if success:
                    failed = 0

                    test_totals_line = test_result_lines[1]
                    total_str = test_totals_line[3]
                    rc = SUCCESS
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
