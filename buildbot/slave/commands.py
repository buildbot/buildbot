# -*- test-case-name: buildbot.test.test_slavecommand -*-

import os, os.path, re, signal, shutil, types, time

from twisted.internet.protocol import ProcessProtocol
from twisted.internet import reactor, defer
from twisted.python import log, failure, runtime

from buildbot.twcompat import implements, which
from buildbot.slave.interfaces import ISlaveCommand
from buildbot.slave.registry import registerSlaveCommand

cvs_ver = '$Revision: 1.51 $'[1+len("Revision: "):-2]

# version history:
#  >=1.17: commands are interruptable
#  >=1.28: Arch understands 'revision', added Bazaar
#  >=1.33: Source classes understand 'retry'
#  >=1.39: Source classes correctly handle changes in branch (except Git)
#          Darcs accepts 'revision' (now all do but Git) (well, and P4Sync)
#          Arch/Baz should accept 'build-config'

class CommandInterrupted(Exception):
    pass
class TimeoutError(Exception):
    pass

class AbandonChain(Exception):
    """A series of chained steps can raise this exception to indicate that
    one of the intermediate ShellCommands has failed, such that there is no
    point in running the remainder. 'rc' should be the non-zero exit code of
    the failing ShellCommand."""

    def __repr__(self):
        return "<AbandonChain rc=%s>" % self.args[0]

def getCommand(name):
    possibles = which(name)
    if not possibles:
        raise RuntimeError("Couldn't find executable for '%s'" % name)
    return possibles[0]

def rmdirRecursive(dir):
    """This is a replacement for shutil.rmtree that works better under
    windows. Thanks to Bear at the OSAF for the code."""
    if not os.path.exists(dir):
        return

    if os.path.islink(dir):
        os.remove(dir)
        return

    for name in os.listdir(dir):
        full_name = os.path.join(dir, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if os.name == 'nt':
            if not os.access(full_name, os.W_OK):
                os.chmod(full_name, 0600)
        if os.path.isdir(full_name):
            rmdirRecursive(full_name)
        else:
            # print "removing file", full_name
            os.remove(full_name)
    os.rmdir(dir)

class ShellCommandPP(ProcessProtocol):
    debug = False

    def __init__(self, command):
        self.command = command

    def connectionMade(self):
        if self.debug:
            log.msg("ShellCommandPP.connectionMade")
        if not self.command.process:
            if self.debug:
                log.msg(" assigning self.command.process: %s" %
                        (self.transport,))
            self.command.process = self.transport

        if self.command.stdin:
            if self.debug: log.msg(" writing to stdin")
            self.transport.write(self.command.stdin)

        # TODO: maybe we shouldn't close stdin when using a PTY. I can't test
        # this yet, recent debian glibc has a bug which causes thread-using
        # test cases to SIGHUP trial, and the workaround is to either run
        # the whole test with /bin/sh -c " ".join(argv)  (way gross) or to
        # not use a PTY. Once the bug is fixed, I'll be able to test what
        # happens when you close stdin on a pty. My concern is that it will
        # SIGHUP the child (since we are, in a sense, hanging up on them).
        # But it may well be that keeping stdout open prevents the SIGHUP
        # from being sent.
        #if not self.command.usePTY:

        if self.debug: log.msg(" closing stdin")
        self.transport.closeStdin()

    def outReceived(self, data):
        if self.debug:
            log.msg("ShellCommandPP.outReceived")
        self.command.addStdout(data)

    def errReceived(self, data):
        if self.debug:
            log.msg("ShellCommandPP.errReceived")
        self.command.addStderr(data)

    def processEnded(self, status_object):
        if self.debug:
            log.msg("ShellCommandPP.processEnded", status_object)
        # status_object is a Failure wrapped around an
        # error.ProcessTerminated or and error.ProcessDone.
        # requires twisted >= 1.0.4 to overcome a bug in process.py
        sig = status_object.value.signal
        rc = status_object.value.exitCode
        self.command.finished(sig, rc)

class ShellCommand:
    # This is a helper class, used by SlaveCommands to run programs in a
    # child shell.

    notreally = False
    BACKUP_TIMEOUT = 5
    KILL = "KILL"

    def __init__(self, builder, command,
                 workdir, environ=None,
                 sendStdout=True, sendStderr=True, sendRC=True,
                 timeout=None, stdin=None, keepStdout=False):
        """

        @param keepStdout: if True, we keep a copy of all the stdout text
                           that we've seen. This copy is available in
                           self.stdout, which can be read after the command
                           has finished.
        """

        self.builder = builder
        self.command = command
        self.sendStdout = sendStdout
        self.sendStderr = sendStderr
        self.sendRC = sendRC
        self.workdir = workdir
        self.environ = os.environ.copy()
        if environ:
            if (self.environ.has_key('PYTHONPATH')
                and environ.has_key('PYTHONPATH')):
                # special case, prepend the builder's items to the existing
                # ones. This will break if you send over empty strings, so
                # don't do that.
                environ['PYTHONPATH'] = (environ['PYTHONPATH']
                                         + os.pathsep
                                         + self.environ['PYTHONPATH'])
                # this will proceed to replace the old one
            self.environ.update(environ)
        self.stdin = stdin
        self.timeout = timeout
        self.timer = None
        self.keepStdout = keepStdout

        # usePTY=True is a convenience for cleaning up all children and
        # grandchildren of a hung command. Fall back to usePTY=False on
        # systems where ptys cause problems.

        self.usePTY = self.builder.usePTY
        if runtime.platformType != "posix":
            self.usePTY = False # PTYs are posix-only
        if stdin is not None:
            # for .closeStdin to matter, we must use a pipe, not a PTY
            self.usePTY = False

    def __repr__(self):
        return "<slavecommand.ShellCommand '%s'>" % self.command

    def sendStatus(self, status):
        self.builder.sendUpdate(status)

    def start(self):
        # return a Deferred which fires (with the exit code) when the command
        # completes
        if self.keepStdout:
            self.stdout = ""
        self.deferred = defer.Deferred()
        try:
            self._startCommand()
        except:
            log.msg("error in ShellCommand._startCommand")
            log.err()
            # pretend it was a shell error
            self.deferred.errback(AbandonChain(-1))
        return self.deferred

    def _startCommand(self):
        log.msg("ShellCommand._startCommand")
        if self.notreally:
            self.sendStatus({'header': "command '%s' in dir %s" % \
                             (self.command, self.workdir)})
            self.sendStatus({'header': "(not really)\n"})
            self.finished(None, 0)
            return

        self.pp = ShellCommandPP(self)

        if type(self.command) in types.StringTypes:
            if runtime.platformType  == 'win32':
                argv = [os.environ['COMSPEC'], '/c', self.command]
            else:
                # for posix, use /bin/sh. for other non-posix, well, doesn't
                # hurt to try
                argv = ['/bin/sh', '-c', self.command]
        else:
            if runtime.platformType  == 'win32':
                argv = [os.environ['COMSPEC'], '/c'] + list(self.command)
            else:
                argv = self.command

        # self.stdin is handled in ShellCommandPP.connectionMade

        # first header line is the command in plain text, argv joined with
        # spaces. You should be able to cut-and-paste this into a shell to
        # obtain the same results. If there are spaces in the arguments, too
        # bad.
        msg = " ".join(argv)
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        # then comes the secondary information
        msg = " in dir %s" % (self.workdir,)
        if self.timeout:
            msg += " (timeout %d secs)" % (self.timeout,)
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        # then the argv array for resolving unambiguity
        msg = " argv: %s" % (argv,)
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        # then the environment, since it sometimes causes problems
        msg = " environment: %s" % (self.environ,)
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        # win32eventreactor's spawnProcess (under twisted <= 2.0.1) returns
        # None, as opposed to all the posixbase-derived reactors (which
        # return the new Process object). This is a nuisance. We can make up
        # for it by having the ProcessProtocol give us their .transport
        # attribute after they get one. I'd prefer to get it from
        # spawnProcess because I'm concerned about returning from this method
        # without having a valid self.process to work with. (if kill() were
        # called right after we return, but somehow before connectionMade
        # were called, then kill() would blow up).
        self.process = None
        p = reactor.spawnProcess(self.pp, argv[0], argv,
                                 self.environ,
                                 self.workdir,
                                 usePTY=self.usePTY)
        # connectionMade might have been called during spawnProcess
        if not self.process:
            self.process = p

        # connectionMade also closes stdin as long as we're not using a PTY.
        # This is intended to kill off inappropriately interactive commands
        # better than the (long) hung-command timeout. ProcessPTY should be
        # enhanced to allow the same childFDs argument that Process takes,
        # which would let us connect stdin to /dev/null .

        if self.timeout:
            self.timer = reactor.callLater(self.timeout, self.doTimeout)

    def addStdout(self, data):
        if self.sendStdout: self.sendStatus({'stdout': data})
        if self.keepStdout: self.stdout += data
        if self.timer: self.timer.reset(self.timeout)

    def addStderr(self, data):
        if self.sendStderr: self.sendStatus({'stderr': data})
        if self.timer: self.timer.reset(self.timeout)

    def finished(self, sig, rc):
        log.msg("command finished with signal %s, exit code %s" % (sig,rc))
        if sig is not None:
            rc = -1
        if self.sendRC:
            if sig is not None:
                self.sendStatus(
                    {'header': "process killed by signal %d\n" % sig})
            self.sendStatus({'rc': rc})
        if self.timer:
            self.timer.cancel()
            self.timer = None
        d = self.deferred
        self.deferred = None
        if d:
            d.callback(rc)
        else:
            log.msg("Hey, command %s finished twice" % self)

    def failed(self, why):
        log.msg("ShellCommand.failed: command failed: %s" % (why,))
        if self.timer:
            self.timer.cancel()
            self.timer = None
        d = self.deferred
        self.deferred = None
        if d:
            d.errback(why)
        else:
            log.msg("Hey, command %s finished twice" % self)

    def doTimeout(self):
        self.timer = None
        msg = "command timed out: %d seconds without output" % self.timeout
        self.kill(msg)

    def kill(self, msg):
        # This may be called by the timeout, or when the user has decided to
        # abort this build.
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if hasattr(self.process, "pid"):
            msg += ", killing pid %d" % self.process.pid
        log.msg(msg)
        self.sendStatus({'header': "\n" + msg + "\n"})

        hit = 0
        if runtime.platformType == "posix":
            try:
                # really want to kill off all child processes too. Process
                # Groups are ideal for this, but that requires
                # spawnProcess(usePTY=1). Try both ways in case process was
                # not started that way.

                # the test suite sets self.KILL=None to tell us we should
                # only pretend to kill the child. This lets us test the
                # backup timer.

                sig = None
                if self.KILL is not None:
                    sig = getattr(signal, "SIG"+ self.KILL, None)

                if self.KILL == None:
                    log.msg("self.KILL==None, only pretending to kill child")
                elif sig is None:
                    log.msg("signal module is missing SIG%s" % self.KILL)
                elif not hasattr(os, "kill"):
                    log.msg("os module is missing the 'kill' function")
                else:
                    log.msg("trying os.kill(-pid, %d)" % (sig,))
                    os.kill(-self.process.pid, sig)
                    log.msg(" signal %s sent successfully" % sig)
                    hit = 1
            except OSError:
                # probably no-such-process, maybe because there is no process
                # group
                pass
        if not hit:
            try:
                if self.KILL is None:
                    log.msg("self.KILL==None, only pretending to kill child")
                else:
                    log.msg("trying process.signalProcess('KILL')")
                    self.process.signalProcess(self.KILL)
                    log.msg(" signal %s sent successfully" % (self.KILL,))
                    hit = 1
            except OSError:
                # could be no-such-process, because they finished very recently
                pass
        if not hit:
            log.msg("signalProcess/os.kill failed both times")

        if runtime.platformType == "posix":
            # we only do this under posix because the win32eventreactor
            # blocks here until the process has terminated, while closing
            # stderr. This is weird.
            self.pp.transport.loseConnection()

        # finished ought to be called momentarily. Just in case it doesn't,
        # set a timer which will abandon the command.
        self.timer = reactor.callLater(self.BACKUP_TIMEOUT,
                                       self.doBackupTimeout)

    def doBackupTimeout(self):
        log.msg("we tried to kill the process, and it wouldn't die.."
                " finish anyway")
        self.timer = None
        self.sendStatus({'header': "SIGKILL failed to kill process\n"})
        if self.sendRC:
            self.sendStatus({'header': "using fake rc=-1\n"})
            self.sendStatus({'rc': -1})
        self.failed(TimeoutError("SIGKILL failed to kill process"))


class Command:
    if implements:
        implements(ISlaveCommand)
    else:
        __implements__ = ISlaveCommand

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
     c = CommandClass(builder, args)
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

    def __init__(self, builder, stepId, args):
        self.builder = builder
        self.stepId = stepId # just for logging
        self.args = args
        self.setup(args)

    def setup(self, args):
        """Override this in a subclass to extract items from the args dict."""
        pass
        
    def start(self):
        """Start the command. self.running will be set just before this is
        called. This method should return a Deferred that will fire when the
        command has completed. The Deferred's argument will be ignored.

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


class SlaveShellCommand(Command):
    """This is a Command which runs a shell command. The args dict contains
    the following keys:

        - ['command'] (required): a shell command to run. If this is a string,
          it will be run with /bin/sh (['/bin/sh', '-c', command]). If it is a
          list (preferred), it will be used directly.
        - ['workdir'] (required): subdirectory in which the command will be run,
          relative to the builder dir
        - ['env']: a dict of environment variables to augment/replace os.environ
        - ['want_stdout']: 0 if stdout should be thrown away
        - ['want_stderr']: 0 if stderr should be thrown away
        - ['not_really']: 1 to skip execution and return rc=0
        - ['timeout']: seconds of silence to tolerate before killing command

    ShellCommand creates the following status messages:
        - {'stdout': data} : when stdout data is available
        - {'stderr': data} : when stderr data is available
        - {'header': data} : when headers (command start/stop) are available
        - {'rc': rc} : when the process has terminated
    """

    def start(self):
        args = self.args
        sendStdout = args.get('want_stdout', True)
        sendStderr = args.get('want_stderr', True)
        # args['workdir'] is relative to Builder directory, and is required.
        assert args['workdir'] is not None
        workdir = os.path.join(self.builder.basedir, args['workdir'])
        timeout = args.get('timeout', None)

        c = ShellCommand(self.builder, args['command'],
                         workdir, environ=args.get('env'),
                         timeout=timeout,
                         sendStdout=sendStdout, sendStderr=sendStderr,
                         sendRC=True)
        self.command = c
        d = self.command.start()
        return d

    def interrupt(self):
        self.interrupted = True
        self.command.kill("command interrupted")


registerSlaveCommand("shell", SlaveShellCommand, cvs_ver)


class DummyCommand(Command):
    """
    I am a dummy no-op command that by default takes 5 seconds to complete.
    See L{buildbot.process.step.RemoteDummy}
    """
    
    def start(self):
        self.d = defer.Deferred()
        log.msg("  starting dummy command [%s]" % self.stepId)
        self.timer = reactor.callLater(1, self.doStatus)
        return self.d

    def interrupt(self):
        if self.interrupted:
            return
        self.timer.cancel()
        self.timer = None
        self.interrupted = True
        self.finished()

    def doStatus(self):
        log.msg("  sending intermediate status")
        self.sendStatus({'stdout': 'data'})
        timeout = self.args.get('timeout', 5) + 1
        self.timer = reactor.callLater(timeout - 1, self.finished)

    def finished(self):
        log.msg("  dummy command finished [%s]" % self.stepId)
        if self.interrupted:
            self.sendStatus({'rc': 1})
        else:
            self.sendStatus({'rc': 0})
        self.d.callback(0)

registerSlaveCommand("dummy", DummyCommand, cvs_ver)


class SourceBase(Command):
    """Abstract base class for Version Control System operations (checkout
    and update). This class extracts the following arguments from the
    dictionary received from the master:

        - ['workdir']:  (required) the subdirectory where the buildable sources
                        should be placed

        - ['mode']:     one of update/copy/clobber/export, defaults to 'update'

        - ['revision']: If not None, this is an int or string which indicates
                        which sources (along a time-like axis) should be used.
                        It is the thing you provide as the CVS -r or -D
                        argument.

        - ['patch']:    If not None, this is a tuple of (striplevel, patch)
                        which contains a patch that should be applied after the
                        checkout has occurred. Once applied, the tree is no
                        longer eligible for use with mode='update', and it only
                        makes sense to use this in conjunction with a
                        ['revision'] argument. striplevel is an int, and patch
                        is a string in standard unified diff format. The patch
                        will be applied with 'patch -p%d <PATCH', with
                        STRIPLEVEL substituted as %d. The command will fail if
                        the patch process fails (rejected hunks).

        - ['timeout']:  seconds of silence tolerated before we kill off the
                        command

        - ['retry']:    If not None, this is a tuple of (delay, repeats)
                        which means that any failed VC updates should be
                        reattempted, up to REPEATS times, after a delay of
                        DELAY seconds. This is intended to deal with slaves
                        that experience transient network failures.
    """

    sourcedata = ""

    def setup(self, args):
        # if we need to parse the output, use this environment. Otherwise
        # command output will be in whatever the buildslave's native language
        # has been set to.
        self.env = os.environ.copy()
        self.env['LC_ALL'] = "C"

        self.workdir = args['workdir']
        self.mode = args.get('mode', "update")
        self.revision = args.get('revision')
        self.patch = args.get('patch')
        self.timeout = args.get('timeout', 120)
        self.retry = args.get('retry')
        # VC-specific subclasses should override this to extract more args.
        # Make sure to upcall!

    def start(self):
        self.sendStatus({'header': "starting " + self.header + "\n"})
        self.command = None

        # self.srcdir is where the VC system should put the sources
        if self.mode == "copy":
            self.srcdir = "source" # hardwired directory name, sorry
        else:
            self.srcdir = self.workdir
        self.sourcedatafile = os.path.join(self.builder.basedir,
                                           self.srcdir,
                                           ".buildbot-sourcedata")

        d = defer.succeed(None)
        # do we need to clobber anything?
        if self.mode in ("copy", "clobber", "export"):
            d.addCallback(self.doClobber, self.workdir)
        if not (self.sourcedirIsUpdateable() and self.sourcedataMatches()):
            # the directory cannot be updated, so we have to clobber it.
            # Perhaps the master just changed modes from 'export' to
            # 'update'.
            d.addCallback(self.doClobber, self.srcdir)

        d.addCallback(self.doVC)

        if self.mode == "copy":
            d.addCallback(self.doCopy)
        if self.patch:
            d.addCallback(self.doPatch)
        d.addCallbacks(self._sendRC, self._checkAbandoned)
        return d

    def interrupt(self):
        self.interrupted = True
        if self.command:
            self.command.kill("command interrupted")

    def doVC(self, res):
        if self.interrupted:
            raise AbandonChain(1)
        if self.sourcedirIsUpdateable() and self.sourcedataMatches():
            d = self.doVCUpdate()
            d.addCallback(self.maybeDoVCFallback)
        else:
            d = self.doVCFull()
            d.addBoth(self.maybeDoVCRetry)
        d.addCallback(self._abandonOnFailure)
        d.addCallback(self._handleGotRevision)
        d.addCallback(self.writeSourcedata)
        return d

    def sourcedataMatches(self):
        try:
            olddata = open(self.sourcedatafile, "r").read()
            if olddata != self.sourcedata:
                return False
        except IOError:
            return False
        return True

    def _handleGotRevision(self, res):
        d = defer.maybeDeferred(self.parseGotRevision)
        d.addCallback(lambda got_revision:
                      self.sendStatus({'got_revision': got_revision}))
        return d

    def parseGotRevision(self):
        """Override this in a subclass. It should return a string that
        represents which revision was actually checked out, or a Deferred
        that will fire with such a string. If, in a future build, you were to
        pass this 'got_revision' string in as the 'revision' component of a
        SourceStamp, you should wind up with the same source code as this
        checkout just obtained.

        It is probably most useful to scan self.command.stdout for a string
        of some sort. Be sure to set keepStdout=True on the VC command that
        you run, so that you'll have something available to look at.

        If this information is unavailable, just return None."""

        return None

    def writeSourcedata(self, res):
        open(self.sourcedatafile, "w").write(self.sourcedata)
        return res

    def sourcedirIsUpdateable(self):
        raise NotImplementedError("this must be implemented in a subclass")

    def doVCUpdate(self):
        raise NotImplementedError("this must be implemented in a subclass")

    def doVCFull(self):
        raise NotImplementedError("this must be implemented in a subclass")

    def maybeDoVCFallback(self, rc):
        if type(rc) is int and rc == 0:
            return rc
        if self.interrupted:
            raise AbandonChain(1)
        msg = "update failed, clobbering and trying again"
        self.sendStatus({'header': msg + "\n"})
        log.msg(msg)
        d = self.doClobber(None, self.srcdir)
        d.addCallback(self.doVCFallback2)
        return d

    def doVCFallback2(self, res):
        msg = "now retrying VC operation"
        self.sendStatus({'header': msg + "\n"})
        log.msg(msg)
        d = self.doVCFull()
        d.addBoth(self.maybeDoVCRetry)
        d.addCallback(self._abandonOnFailure)
        return d

    def maybeDoVCRetry(self, res):
        """We get here somewhere after a VC chain has finished. res could
        be::

         - 0: the operation was successful
         - nonzero: the operation failed. retry if possible
         - AbandonChain: the operation failed, someone else noticed. retry.
         - Failure: some other exception, re-raise
        """

        if isinstance(res, failure.Failure):
            if self.interrupted:
                return res # don't re-try interrupted builds
            res.trap(AbandonChain)
        else:
            if type(res) is int and res == 0:
                return res
            if self.interrupted:
                raise AbandonChain(1)
        # if we get here, we should retry, if possible
        if self.retry:
            delay, repeats = self.retry
            if repeats >= 0:
                self.retry = (delay, repeats-1)
                msg = ("update failed, trying %d more times after %d seconds"
                       % (repeats, delay))
                self.sendStatus({'header': msg + "\n"})
                log.msg(msg)
                d = defer.Deferred()
                d.addCallback(lambda res: self.doVCFull())
                d.addBoth(self.maybeDoVCRetry)
                reactor.callLater(delay, d.callback, None)
                return d
        return res

    def doClobber(self, dummy, dirname):
        # TODO: remove the old tree in the background
##         workdir = os.path.join(self.builder.basedir, self.workdir)
##         deaddir = self.workdir + ".deleting"
##         if os.path.isdir(workdir):
##             try:
##                 os.rename(workdir, deaddir)
##                 # might fail if deaddir already exists: previous deletion
##                 # hasn't finished yet
##                 # start the deletion in the background
##                 # TODO: there was a solaris/NetApp/NFS problem where a
##                 # process that was still running out of the directory we're
##                 # trying to delete could prevent the rm-rf from working. I
##                 # think it stalled the rm, but maybe it just died with
##                 # permission issues. Try to detect this.
##                 os.commands("rm -rf %s &" % deaddir)
##             except:
##                 # fall back to sequential delete-then-checkout
##                 pass
        d = os.path.join(self.builder.basedir, dirname)
        if runtime.platformType != "posix":
            # if we're running on w32, use rmtree instead. It will block,
            # but hopefully it won't take too long.
            rmdirRecursive(d)
            return defer.succeed(0)
        command = ["rm", "-rf", d]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=0, timeout=self.timeout)
        self.command = c
        # sendRC=0 means the rm command will send stdout/stderr to the
        # master, but not the rc=0 when it finishes. That job is left to
        # _sendRC
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d

    def doCopy(self, res):
        # now copy tree to workdir
        fromdir = os.path.join(self.builder.basedir, self.srcdir)
        todir = os.path.join(self.builder.basedir, self.workdir)
        if runtime.platformType != "posix":
            shutil.copytree(fromdir, todir)
            return defer.succeed(0)
        command = ['cp', '-r', '-p', fromdir, todir]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d

    def doPatch(self, res):
        patchlevel, diff = self.patch
        command = [getCommand("patch"), '-p%d' % patchlevel]
        dir = os.path.join(self.builder.basedir, self.workdir)
        # mark the directory so we don't try to update it later
        open(os.path.join(dir, ".buildbot-patched"), "w").write("patched\n")
        # now apply the patch
        c = ShellCommand(self.builder, command, dir,
                         sendRC=False, timeout=self.timeout,
                         stdin=diff)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d


class CVS(SourceBase):
    """CVS-specific VC operation. In addition to the arguments handled by
    SourceBase, this command reads the following keys:

    ['cvsroot'] (required): the CVSROOT repository string
    ['cvsmodule'] (required): the module to be retrieved
    ['branch']: a '-r' tag or branch name to use for the checkout/update
    ['login']: a string for use as a password to 'cvs login'
    ['global_options']: a list of strings to use before the CVS verb
    """

    header = "cvs operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("cvs")
        self.cvsroot = args['cvsroot']
        self.cvsmodule = args['cvsmodule']
        self.global_options = args.get('global_options', [])
        self.branch = args.get('branch')
        self.login = args.get('login')
        self.sourcedata = "%s\n%s\n%s\n" % (self.cvsroot, self.cvsmodule,
                                            self.branch)

    def sourcedirIsUpdateable(self):
        if os.path.exists(os.path.join(self.builder.basedir,
                                       self.srcdir, ".buildbot-patched")):
            return False
        return os.path.isdir(os.path.join(self.builder.basedir,
                                          self.srcdir, "CVS"))

    def start(self):
        if self.login is not None:
            # need to do a 'cvs login' command first
            d = self.builder.basedir
            command = ([self.vcexe, '-d', self.cvsroot] + self.global_options
                       + ['login'])
            c = ShellCommand(self.builder, command, d,
                             sendRC=False, timeout=self.timeout,
                             stdin=self.login+"\n")
            self.command = c
            d = c.start()
            d.addCallback(self._abandonOnFailure)
            d.addCallback(self._didLogin)
            return d
        else:
            return self._didLogin(None)

    def _didLogin(self, res):
        # now we really start
        return SourceBase.start(self)

    def doVCUpdate(self):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, '-z3'] + self.global_options + ['update', '-dP']
        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        return c.start()

    def doVCFull(self):
        d = self.builder.basedir
        if self.mode == "export":
            verb = "export"
        else:
            verb = "checkout"
        command = ([self.vcexe, '-d', self.cvsroot, '-z3'] +
                   self.global_options +
                   [verb, '-d', self.srcdir])
        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        command += [self.cvsmodule]
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        return c.start()

    def parseGotRevision(self):
        # CVS does not have any kind of revision stamp to speak of. We return
        # the current timestamp as a best-effort guess, but this depends upon
        # the local system having a clock that is
        # reasonably-well-synchronized with the repository.
        return time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime())

registerSlaveCommand("cvs", CVS, cvs_ver)

class SVN(SourceBase):
    """Subversion-specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['svnurl'] (required): the SVN repository string
    """

    header = "svn operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("svn")
        self.svnurl = args['svnurl']
        self.sourcedata = "%s\n" % self.svnurl

    def sourcedirIsUpdateable(self):
        if os.path.exists(os.path.join(self.builder.basedir,
                                       self.srcdir, ".buildbot-patched")):
            return False
        return os.path.isdir(os.path.join(self.builder.basedir,
                                          self.srcdir, ".svn"))

    def doVCUpdate(self):
        revision = self.args['revision'] or 'HEAD'
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'update', '--revision', str(revision)]
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         keepStdout=True)
        self.command = c
        return c.start()

    def doVCFull(self):
        revision = self.args['revision'] or 'HEAD'
        d = self.builder.basedir
        if self.mode == "export":
            command = [self.vcexe, 'export', '--revision', str(revision),
                       self.svnurl, self.srcdir]
        else:
            # mode=='clobber', or copy/update on a broken workspace
            command = [self.vcexe, 'checkout', '--revision', str(revision),
                       self.svnurl, self.srcdir]
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         keepStdout=True)
        self.command = c
        return c.start()

    def parseGotRevision(self):
        # svn checkout operations finish with 'Checked out revision 16657.'
        # svn update operations finish the line 'At revision 16654.'
        # But we don't use those. Instead, run 'svnversion'.
        svnversion_command = getCommand("svnversion")
        # older versions of 'svnversion' (1.1.4) require the WC_PATH
        # argument, newer ones (1.3.1) do not.
        command = [svnversion_command, "."]
        c = ShellCommand(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True)
        c.usePTY = False
        d = c.start()
        def _parse(res):
            r = c.stdout.strip()
            got_version = None
            try:
                got_version = int(r)
            except ValueError:
                msg =("SVN.parseGotRevision unable to parse output "
                      "of svnversion: '%s'" % r)
                log.msg(msg)
                self.sendStatus({'header': msg + "\n"})
            return got_version
        d.addCallback(_parse)
        return d


registerSlaveCommand("svn", SVN, cvs_ver)

class Darcs(SourceBase):
    """Darcs-specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['repourl'] (required): the Darcs repository string
    """

    header = "darcs operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("darcs")
        self.repourl = args['repourl']
        self.sourcedata = "%s\n" % self.repourl
        self.revision = self.args.get('revision')

    def sourcedirIsUpdateable(self):
        if os.path.exists(os.path.join(self.builder.basedir,
                                       self.srcdir, ".buildbot-patched")):
            return False
        if self.revision:
            # checking out a specific revision requires a full 'darcs get'
            return False
        return os.path.isdir(os.path.join(self.builder.basedir,
                                          self.srcdir, "_darcs"))

    def doVCUpdate(self):
        assert not self.revision
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'pull', '--all', '--verbose']
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        return c.start()

    def doVCFull(self):
        # checkout or export
        d = self.builder.basedir
        command = [self.vcexe, 'get', '--verbose', '--partial',
                   '--repo-name', self.srcdir]
        if self.revision:
            # write the context to a file
            n = os.path.join(self.builder.basedir, ".darcs-context")
            f = open(n, "wb")
            f.write(self.revision)
            f.close()
            # tell Darcs to use that context
            command.append('--context')
            command.append(n)
        command.append(self.repourl)

        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        d = c.start()
        if self.revision:
            d.addCallback(self.removeContextFile, n)
        return d

    def removeContextFile(self, res, n):
        os.unlink(n)
        return res

    def parseGotRevision(self):
        # we use 'darcs context' to find out what we wound up with
        command = [self.vcexe, "changes", "--context"]
        c = ShellCommand(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True)
        c.usePTY = False
        d = c.start()
        d.addCallback(lambda res: c.stdout)
        return d

registerSlaveCommand("darcs", Darcs, cvs_ver)

class Git(SourceBase):
    """Git specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['repourl'] (required): the Cogito repository string
    """

    header = "git operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.repourl = args['repourl']
        #self.sourcedata = "" # TODO

    def sourcedirIsUpdateable(self):
        if os.path.exists(os.path.join(self.builder.basedir,
                                       self.srcdir, ".buildbot-patched")):
            return False
        return os.path.isdir(os.path.join(self.builder.basedir,
                                          self.srcdir, ".git"))

    def doVCUpdate(self):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = ['cg-update']
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        return c.start()

    def doVCFull(self):
        d = os.path.join(self.builder.basedir, self.srcdir)
        os.mkdir(d)
        command = ['cg-clone', '-s', self.repourl]
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        return c.start()

registerSlaveCommand("git", Git, cvs_ver)

class Arch(SourceBase):
    """Arch-specific (tla-specific) VC operation. In addition to the
    arguments handled by SourceBase, this command reads the following keys:

    ['url'] (required): the repository string
    ['version'] (required): which version (i.e. branch) to retrieve
    ['revision'] (optional): the 'patch-NN' argument to check out
    ['archive']: the archive name to use. If None, use the archive's default
    ['build-config']: if present, give to 'tla build-config' after checkout
    """

    header = "arch operation"
    buildconfig = None

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("tla")
        self.archive = args.get('archive')
        self.url = args['url']
        self.version = args['version']
        self.revision = args.get('revision')
        self.buildconfig = args.get('build-config')
        self.sourcedata = "%s\n%s\n%s\n" % (self.url, self.version,
                                            self.buildconfig)

    def sourcedirIsUpdateable(self):
        if self.revision:
            # Arch cannot roll a directory backwards, so if they ask for a
            # specific revision, clobber the directory. Technically this
            # could be limited to the cases where the requested revision is
            # later than our current one, but it's too hard to extract the
            # current revision from the tree.
            return False
        if os.path.exists(os.path.join(self.builder.basedir,
                                       self.srcdir, ".buildbot-patched")):
            return False
        return os.path.isdir(os.path.join(self.builder.basedir,
                                          self.srcdir, "{arch}"))

    def doVCUpdate(self):
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'replay']
        if self.revision:
            command.append(self.revision)
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        return c.start()

    def doVCFull(self):
        # to do a checkout, we must first "register" the archive by giving
        # the URL to tla, which will go to the repository at that URL and
        # figure out the archive name. tla will tell you the archive name
        # when it is done, and all further actions must refer to this name.

        command = [self.vcexe, 'register-archive', '--force', self.url]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, keepStdout=True,
                         timeout=self.timeout)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        d.addCallback(self._didRegister, c)
        return d

    def _didRegister(self, res, c):
        # find out what tla thinks the archive name is. If the user told us
        # to use something specific, make sure it matches.
        r = re.search(r'Registering archive: (\S+)\s*$', c.stdout)
        if r:
            msg = "tla reports archive name is '%s'" % r.group(1)
            log.msg(msg)
            self.builder.sendUpdate({'header': msg+"\n"})
            if self.archive and r.group(1) != self.archive:
                msg = (" mismatch, we wanted an archive named '%s'"
                       % self.archive)
                log.msg(msg)
                self.builder.sendUpdate({'header': msg+"\n"})
                raise AbandonChain(-1)
            self.archive = r.group(1)
        assert self.archive, "need archive name to continue"
        return self._doGet()

    def _doGet(self):
        ver = self.version
        if self.revision:
            ver += "--%s" % self.revision
        command = [self.vcexe, 'get', '--archive', self.archive,
                   '--no-pristine',
                   ver, self.srcdir]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        if self.buildconfig:
            d.addCallback(self._didGet)
        return d

    def _didGet(self, res):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'build-config', self.buildconfig]
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d

    def parseGotRevision(self):
        # using code from tryclient.TlaExtractor
        # 'tla logs --full' gives us ARCHIVE/BRANCH--REVISION
        # 'tla logs' gives us REVISION
        command = [self.vcexe, "logs", "--full", "--reverse"]
        c = ShellCommand(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True)
        c.usePTY = False
        d = c.start()
        def _parse(res):
            tid = c.stdout.split("\n")[0].strip()
            slash = tid.index("/")
            dd = tid.rindex("--")
            #branch = tid[slash+1:dd]
            baserev = tid[dd+2:]
            return baserev
        d.addCallback(_parse)
        return d

registerSlaveCommand("arch", Arch, cvs_ver)

class Bazaar(Arch):
    """Bazaar (/usr/bin/baz) is an alternative client for Arch repositories.
    It is mostly option-compatible, but archive registration is different
    enough to warrant a separate Command.

    ['archive'] (required): the name of the archive being used
    """

    def setup(self, args):
        Arch.setup(self, args)
        self.vcexe = getCommand("baz")
        # baz doesn't emit the repository name after registration (and
        # grepping through the output of 'baz archives' is too hard), so we
        # require that the buildmaster configuration to provide both the
        # archive name and the URL.
        self.archive = args['archive'] # required for Baz
        self.sourcedata = "%s\n%s\n%s\n" % (self.url, self.version,
                                            self.buildconfig)

    # in _didRegister, the regexp won't match, so we'll stick with the name
    # in self.archive

    def _doGet(self):
        # baz prefers ARCHIVE/VERSION. This will work even if
        # my-default-archive is not set.
        ver = self.archive + "/" + self.version
        if self.revision:
            ver += "--%s" % self.revision
        command = [self.vcexe, 'get', '--no-pristine',
                   ver, self.srcdir]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        if self.buildconfig:
            d.addCallback(self._didGet)
        return d

    def parseGotRevision(self):
        # using code from tryclient.BazExtractor
        command = [self.vcexe, "tree-id"]
        c = ShellCommand(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True)
        c.usePTY = False
        d = c.start()
        def _parse(res):
            tid = c.stdout.strip()
            slash = tid.index("/")
            dd = tid.rindex("--")
            #branch = tid[slash+1:dd]
            baserev = tid[dd+2:]
            return baserev
        d.addCallback(_parse)
        return d

registerSlaveCommand("bazaar", Bazaar, cvs_ver)


class Mercurial(SourceBase):
    """Mercurial specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['repourl'] (required): the Cogito repository string
    """

    header = "mercurial operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("hg")
        self.repourl = args['repourl']
        self.sourcedata = "%s\n" % self.repourl
        self.stdout = ""
        self.stderr = ""

    def sourcedirIsUpdateable(self):
        if os.path.exists(os.path.join(self.builder.basedir,
                                       self.srcdir, ".buildbot-patched")):
            return False
        # like Darcs, to check out a specific (old) revision, we have to do a
        # full checkout. TODO: I think 'hg pull' plus 'hg update' might work
        if self.revision:
            return False
        return os.path.isdir(os.path.join(self.builder.basedir,
                                          self.srcdir, ".hg"))

    def doVCUpdate(self):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'pull', '--update', '--verbose']
        if self.args['revision']:
            command.extend(['--rev', self.args['revision']])
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         keepStdout=True)
        self.command = c
        d = c.start()
        d.addCallback(self._handleEmptyUpdate)
        return d

    def _handleEmptyUpdate(self, res):
        if type(res) is int and res == 1:
            if self.command.stdout.find("no changes found") != -1:
                # 'hg pull', when it doesn't have anything to do, exits with
                # rc=1, and there appears to be no way to shut this off. It
                # emits a distinctive message to stdout, though. So catch
                # this and pretend that it completed successfully.
                return 0
        return res

    def doVCFull(self):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'clone']
        if self.args['revision']:
            command.extend(['--rev', self.args['revision']])
        command.extend([self.repourl, d])
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        return c.start()

    def parseGotRevision(self):
        # we use 'hg identify' to find out what we wound up with
        command = [self.vcexe, "identify"]
        c = ShellCommand(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True)
        d = c.start()
        def _parse(res):
            m = re.search(r'^(\w+)', c.stdout)
            return m.group(1)
        d.addCallback(_parse)
        return d

registerSlaveCommand("hg", Mercurial, cvs_ver)


class P4Sync(SourceBase):
    """A partial P4 source-updater. Requires manual setup of a per-slave P4
    environment. The only thing which comes from the master is P4PORT.
    'mode' is required to be 'copy'.

    ['p4port'] (required): host:port for server to access
    ['p4user'] (optional): user to use for access
    ['p4passwd'] (optional): passwd to try for the user
    ['p4client'] (optional): client spec to use
    """

    header = "p4 sync"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("p4")
        self.p4port = args['p4port']
        self.p4user = args['p4user']
        self.p4passwd = args['p4passwd']
        self.p4client = args['p4client']

    def sourcedirIsUpdateable(self):
        return True

    def doVCUpdate(self):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe]
        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            command.extend(['-P', self.p4passwd])
        if self.p4client:
            command.extend(['-c', self.p4client])
        command.extend(['sync'])
        if self.revision:
            command.extend(['@' + self.revision])
        env = {}
        c = ShellCommand(self.builder, command, d, environ=env,
                         sendRC=False, timeout=self.timeout)
        self.command = c
        return c.start()

    def doVCFull(self):
        return self.doVCUpdate()

registerSlaveCommand("p4sync", P4Sync, cvs_ver)
