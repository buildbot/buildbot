import os, types
from twisted.python import runtime
from twisted.internet import reactor 
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE
from twisted.internet.protocol import ProcessProtocol

class MasterShellCommand(BuildStep):
    """
    Run a shell command locally - on the buildmaster.  The shell command
    COMMAND is specified just as for a RemoteShellCommand.  Note that extra
    logfiles are not sopported.
    """
    name='MasterShellCommand'
    description='Running'
    descriptionDone='Ran'

    def __init__(self, command,
                 description=None, descriptionDone=None,
                 **kwargs):
        BuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(description=description,
                                 descriptionDone=descriptionDone,
                                 command=command)

        self.command=command
        if description:
            self.description = description
        if isinstance(self.description, str):
            self.description = [self.description]
        if descriptionDone:
            self.descriptionDone = descriptionDone
        if isinstance(self.descriptionDone, str):
            self.descriptionDone = [self.descriptionDone]

    class LocalPP(ProcessProtocol):
        def __init__(self, step):
            self.step = step

        def outReceived(self, data):
            self.step.stdio_log.addStdout(data)

        def errReceived(self, data):
            self.step.stdio_log.addStderr(data)

        def processEnded(self, status_object):
            self.step.stdio_log.addHeader("exit status %d\n" % status_object.value.exitCode)
            self.step.processEnded(status_object)

    def start(self):
        # render properties
        properties = self.build.getProperties()
        command = properties.render(self.command)
        # set up argv
        if type(command) in types.StringTypes:
            if runtime.platformType  == 'win32':
                argv = os.environ['COMSPEC'].split() # allow %COMSPEC% to have args
                if '/c' not in argv: argv += ['/c'] 
                argv += [command]
            else:
                # for posix, use /bin/sh. for other non-posix, well, doesn't
                # hurt to try
                argv = ['/bin/sh', '-c', command]
        else:
            if runtime.platformType  == 'win32':
                argv = os.environ['COMSPEC'].split() # allow %COMSPEC% to have args
                if '/c' not in argv: argv += ['/c'] 
                argv += list(command)
            else:
                argv = command

        self.stdio_log = stdio_log = self.addLog("stdio")

        if type(command) in types.StringTypes:
            stdio_log.addHeader(command.strip() + "\n\n")
        else:
            stdio_log.addHeader(" ".join(command) + "\n\n")
        stdio_log.addHeader("** RUNNING ON BUILDMASTER **\n")
        stdio_log.addHeader(" in dir %s\n" % os.getcwd())
        stdio_log.addHeader(" argv: %s\n" % (argv,))
        self.step_status.setText(list(self.description))

        # TODO add a timeout?
        reactor.spawnProcess(self.LocalPP(self), argv[0], argv)
        # (the LocalPP object will call processEnded for us)

    def processEnded(self, status_object):
        if status_object.value.exitCode != 0:
            self.step_status.setText(["failed (%d)" % status_object.value.exitCode])
            self.finished(FAILURE)
        else:
            self.step_status.setText(list(self.descriptionDone))
            self.finished(SUCCESS)
