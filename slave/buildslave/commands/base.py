
import os, signal, types, re, traceback
from stat import ST_CTIME, ST_MTIME, ST_SIZE

from zope.interface import implements
from twisted.internet import reactor, defer, task
from twisted.python import log, runtime

from buildslave.interfaces import ISlaveCommand
from buildslave import runprocess
from buildslave.commands.registry import registerSlaveCommand
from buildslave.exceptions import AbandonChain
from buildslave import util

# this used to be a CVS $-style "Revision" auto-updated keyword, but since I
# moved to Darcs as the primary repository, this is updated manually each
# time this file is changed. The last cvs_ver that was here was 1.51 .
command_version = "2.9"

# version history:
#  >=1.17: commands are interruptable
#  >=1.28: Arch understands 'revision', added Bazaar
#  >=1.33: Source classes understand 'retry'
#  >=1.39: Source classes correctly handle changes in branch (except Git)
#          Darcs accepts 'revision' (now all do but Git) (well, and P4Sync)
#          Arch/Baz should accept 'build-config'
#  >=1.51: (release 0.7.3)
#  >= 2.1: SlaveShellCommand now accepts 'initial_stdin', 'keep_stdin_open',
#          and 'logfiles'. It now sends 'log' messages in addition to
#          stdout/stdin/header/rc. It acquired writeStdin/closeStdin methods,
#          but these are not remotely callable yet.
#          (not externally visible: ShellCommandPP has writeStdin/closeStdin.
#          ShellCommand accepts new arguments (logfiles=, initialStdin=,
#          keepStdinOpen=) and no longer accepts stdin=)
#          (release 0.7.4)
#  >= 2.2: added monotone, uploadFile, and downloadFile (release 0.7.5)
#  >= 2.3: added bzr (release 0.7.6)
#  >= 2.4: Git understands 'revision' and branches
#  >= 2.5: workaround added for remote 'hg clone --rev REV' when hg<0.9.2
#  >= 2.6: added uploadDirectory
#  >= 2.7: added usePTY option to SlaveShellCommand
#  >= 2.8: added username and password args to SVN class
#  >= 2.9: add depth arg to SVN class
#  >= 2.10: CVS can handle 'extra_options' and 'export_options'

class Command:
    implements(ISlaveCommand)

    """This class defines one command that can be invoked by the build master.
    The command is executed on the slave side, and always sends back a
    completion message when it finishes. It may also send intermediate status
    as it runs (by calling builder.sendStatus). Some commands can be
    interrupted (either by the build master or a local timeout), in which
    case the step is expected to complete normally with a status message that
    indicates an error occurred.

    These commands are used by BuildSteps on the master side. Each kind of
    BuildStep uses a single Command. The slave must implement all the
    Commands required by the set of BuildSteps used for any given build:
    this is checked at startup time.

    All Commands are constructed with the same signature:
     c = CommandClass(builder, stepid, args)
    where 'builder' is the parent SlaveBuilder object, and 'args' is a
    dict that is interpreted per-command.

    The setup(args) method is available for setup, and is run from __init__.

    The Command is started with start(). This method must be implemented in a
    subclass, and it should return a Deferred. When your step is done, you
    should fire the Deferred (the results are not used). If the command is
    interrupted, it should fire the Deferred anyway.

    While the command runs. it may send status messages back to the
    buildmaster by calling self.sendStatus(statusdict). The statusdict is
    interpreted by the master-side BuildStep however it likes.

    A separate completion message is sent when the deferred fires, which
    indicates that the Command has finished, but does not carry any status
    data. If the Command needs to return an exit code of some sort, that
    should be sent as a regular status message before the deferred is fired .
    Once builder.commandComplete has been run, no more status messages may be
    sent.

    If interrupt() is called, the Command should attempt to shut down as
    quickly as possible. Child processes should be killed, new ones should
    not be started. The Command should send some kind of error status update,
    then complete as usual by firing the Deferred.

    .interrupted should be set by interrupt(), and can be tested to avoid
    sending multiple error status messages.

    If .running is False, the bot is shutting down (or has otherwise lost the
    connection to the master), and should not send any status messages. This
    is checked in Command.sendStatus .

    """

    # builder methods:
    #  sendStatus(dict) (zero or more)
    #  commandComplete() or commandInterrupted() (one, at end)

    debug = False
    interrupted = False
    running = False # set by Builder, cleared on shutdown or when the
                    # Deferred fires

    _reactor = reactor

    def __init__(self, builder, stepId, args):
        self.builder = builder
        self.stepId = stepId # just for logging
        self.args = args
        self.setup(args)

    def setup(self, args):
        """Override this in a subclass to extract items from the args dict."""
        pass

    def doStart(self):
        self.running = True
        d = defer.maybeDeferred(self.start)
        def commandComplete(res):
            self.running = False
            return res
        d.addBoth(commandComplete)
        return d

    def start(self):
        """Start the command. This method should return a Deferred that will
        fire when the command has completed. The Deferred's argument will be
        ignored.

        This method should be overridden by subclasses."""
        raise NotImplementedError, "You must implement this in a subclass"

    def sendStatus(self, status):
        """Send a status update to the master."""
        if self.debug:
            log.msg("sendStatus", status)
        if not self.running:
            log.msg("would sendStatus but not .running")
            return
        self.builder.sendUpdate(status)

    def doInterrupt(self):
        self.running = False
        self.interrupt()

    def interrupt(self):
        """Override this in a subclass to allow commands to be interrupted.
        May be called multiple times, test and set self.interrupted=True if
        this matters."""
        pass

    # utility methods, mostly used by SlaveShellCommand and the like

    def _abandonOnFailure(self, rc):
        if type(rc) is not int:
            log.msg("weird, _abandonOnFailure was given rc=%s (%s)" % \
                    (rc, type(rc)))
        assert isinstance(rc, int)
        if rc != 0:
            raise AbandonChain(rc)
        return rc

    def _sendRC(self, res):
        self.sendStatus({'rc': 0})

    def _checkAbandoned(self, why):
        log.msg("_checkAbandoned", why)
        why.trap(AbandonChain)
        log.msg(" abandoning chain", why.value)
        self.sendStatus({'rc': why.value.args[0]})
        return None
