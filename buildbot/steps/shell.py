# -*- test-case-name: buildbot.test.test_steps,buildbot.test.test_properties -*-

import types, re
from twisted.python import log
from buildbot.process.buildstep import LoggingBuildStep, RemoteShellCommand, render
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE

# for existing configurations that import WithProperties from here
from buildbot.process.buildstep import WithProperties

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
            self.command = command

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
        self.remote_kwargs = kwargs
        # we need to stash the RemoteShellCommand's args too
        self.addFactoryArguments(**kwargs)

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

        if done and self.descriptionDone is not None:
            return self.descriptionDone
        if self.description is not None:
            return self.description

        words = self.command
        if isinstance(words, types.StringTypes):
            words = words.split()
        # render() each word to handle WithProperties objects
        words = [render(word, self.build) for word in words]
        if len(words) < 1:
            return ["???"]
        if len(words) == 1:
            return ["'%s'" % words[0]]
        if len(words) == 2:
            return ["'%s" % words[0], "%s'" % words[1]]
        return ["'%s" % words[0], "%s" % words[1], "...'"]

    def _interpolateProperties(self, value):
        """
        Expand the L{WithProperties} objects in L{value}
        """
        if isinstance(value, types.StringTypes) or \
           isinstance(value, types.BooleanType) or \
           isinstance(value, types.IntType) or \
           isinstance(value, types.FloatType):
            return value

        if isinstance(value, types.ListType):
            return [self._interpolateProperties(val) for val in value]

        if isinstance(value, types.TupleType):
            return tuple([self._interpolateProperties(val) for val in value])

        if isinstance(value, types.DictType):
            new_dict = { }
            for key, val in value.iteritems():
                new_key = self._interpolateProperties(key)
                new_dict[new_key] = self._interpolateProperties(val)
            return new_dict

        # To make sure we catch anything we forgot
        assert isinstance(value, WithProperties), \
               "%s (%s) is not a WithProperties" % (value, type(value))

        return value.render(self.build)

    def _interpolateWorkdir(self, workdir):
        return render(workdir, self.build)

    def setupEnvironment(self, cmd):
        # merge in anything from Build.slaveEnvironment . Earlier steps
        # (perhaps ones which compile libraries or sub-projects that need to
        # be referenced by later steps) can add keys to
        # self.build.slaveEnvironment to affect later steps.
        slaveEnv = self.build.slaveEnvironment
        if slaveEnv:
            if cmd.args['env'] is None:
                cmd.args['env'] = {}
            cmd.args['env'].update(self._interpolateProperties(slaveEnv))
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
        for logname,remotefilename in self.logfiles.items():
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
        command = self._interpolateProperties(self.command)
        assert isinstance(command, (list, tuple, str))
        # create the actual RemoteShellCommand instance now
        kwargs = self._interpolateProperties(self.remote_kwargs)
        kwargs['workdir'] = self._interpolateWorkdir(kwargs['workdir'])
        kwargs['command'] = command
        kwargs['logfiles'] = self.logfiles
        cmd = RemoteShellCommand(**kwargs)
        self.setupEnvironment(cmd)
        self.checkForOldSlaveAndLogfiles()

        self.startCommand(cmd)



class TreeSize(ShellCommand):
    name = "treesize"
    command = ["du", "-s", "-k", "."]
    kib = None

    def commandComplete(self, cmd):
        out = cmd.logs['stdio'].getText()
        m = re.search(r'^(\d+)', out)
        if m:
            self.kib = int(m.group(1))
            self.setProperty("tree-size-KiB", self.kib)

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

class Configure(ShellCommand):

    name = "configure"
    haltOnFailure = 1
    description = ["configuring"]
    descriptionDone = ["configure"]
    command = ["./configure"]

class WarningCountingShellCommand(ShellCommand):
    warnCount = 0
    warningPattern = '.*warning[: ].*'

    def __init__(self, **kwargs):
        # See if we've been given a regular expression to use to match
        # warnings. If not, use a default that assumes any line with "warning"
        # present is a warning. This may lead to false positives in some cases.
        wp = None
        if kwargs.has_key('warningPattern'):
            wp = kwargs['warningPattern']
            del kwargs['warningPattern']
            self.warningPattern = wp

        # And upcall to let the base class do its work
        ShellCommand.__init__(self, **kwargs)

        if wp:
            self.addFactoryArguments(warningPattern=wp)

    def createSummary(self, log):
        self.warnCount = 0

        # Now compile a regular expression from whichever warning pattern we're
        # using
        if not self.warningPattern:
            return

        wre = self.warningPattern
        if isinstance(wre, str):
            wre = re.compile(wre)

        # Check if each line in the output from this command matched our
        # warnings regular expressions. If did, bump the warnings count and
        # add the line to the collection of lines with warnings
        warnings = []
        # TODO: use log.readlines(), except we need to decide about stdout vs
        # stderr
        for line in log.getText().split("\n"):
            if wre.match(line):
                warnings.append(line)
                self.warnCount += 1

        # If there were any warnings, make the log if lines with warnings
        # available
        if self.warnCount:
            self.addCompleteLog("warnings", "\n".join(warnings) + "\n")

        try:
            old_count = self.getProperty("warnings-count")
        except KeyError:
            old_count = 0
        self.setProperty("warnings-count", old_count + self.warnCount)


    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
            return FAILURE
        if self.warnCount:
            return WARNINGS
        return SUCCESS


class Compile(WarningCountingShellCommand):

    name = "compile"
    haltOnFailure = 1
    description = ["compiling"]
    descriptionDone = ["compile"]
    command = ["make", "all"]

    OFFprogressMetrics = ('output',)
    # things to track: number of files compiled, number of directories
    # traversed (assuming 'make' is being used)

    def createSummary(self, cmd):
        # TODO: grep for the characteristic GCC error lines and
        # assemble them into a pair of buffers
        WarningCountingShellCommand.createSummary(self, cmd)
        pass

class Test(WarningCountingShellCommand):

    name = "test"
    warnOnFailure = 1
    description = ["testing"]
    descriptionDone = ["test"]
    command = ["make", "test"]
