# -*- test-case-name: buildbot.test.test_slavecommand -*-

import os, sys, re, signal, shutil, types, time, tarfile, tempfile
from stat import ST_CTIME, ST_MTIME, ST_SIZE
from xml.dom.minidom import parseString

from zope.interface import implements
from twisted.internet.protocol import ProcessProtocol
from twisted.internet import reactor, defer, task
from twisted.python import log, failure, runtime
from twisted.python.procutils import which

from buildbot.slave.interfaces import ISlaveCommand
from buildbot.slave.registry import registerSlaveCommand
from buildbot.util import to_text, remove_userpassword

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

class CommandInterrupted(Exception):
    pass
class TimeoutError(Exception):
    pass

class Obfuscated:
    """An obfuscated string in a command"""
    def __init__(self, real, fake):
        self.real = real
        self.fake = fake

    def __str__(self):
        return self.fake

    def __repr__(self):
        return `self.fake`

    def get_real(command):
        rv = command
        if type(command) == types.ListType:
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.real)
                else:
                    rv.append(to_text(elt))
        return rv
    get_real = staticmethod(get_real)

    def get_fake(command):
        rv = command
        if type(command) == types.ListType:
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.fake)
                else:
                    rv.append(to_text(elt))
        return rv
    get_fake = staticmethod(get_fake)

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

    # Verify the directory is read/write/execute for the current user
    os.chmod(dir, 0700)

    for name in os.listdir(dir):
        full_name = os.path.join(dir, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if os.name == 'nt':
            if not os.access(full_name, os.W_OK):
                # I think this is now redundant, but I don't have an NT
                # machine to test on, so I'm going to leave it in place
                # -warner
                os.chmod(full_name, 0600)

        if os.path.isdir(full_name):
            rmdirRecursive(full_name)
        else:
            if os.path.isfile(full_name):
                os.chmod(full_name, 0700)
            os.remove(full_name)
    os.rmdir(dir)

class ShellCommandPP(ProcessProtocol):
    debug = False

    def __init__(self, command):
        self.command = command
        self.pending_stdin = ""
        self.stdin_finished = False

    def writeStdin(self, data):
        assert not self.stdin_finished
        if self.connected:
            self.transport.write(data)
        else:
            self.pending_stdin += data

    def closeStdin(self):
        if self.connected:
            if self.debug: log.msg(" closing stdin")
            self.transport.closeStdin()
        self.stdin_finished = True

    def connectionMade(self):
        if self.debug:
            log.msg("ShellCommandPP.connectionMade")
        if not self.command.process:
            if self.debug:
                log.msg(" assigning self.command.process: %s" %
                        (self.transport,))
            self.command.process = self.transport

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

        if self.pending_stdin:
            if self.debug: log.msg(" writing to stdin")
            self.transport.write(self.pending_stdin)
        if self.stdin_finished:
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

class LogFileWatcher:
    POLL_INTERVAL = 2

    def __init__(self, command, name, logfile, follow=False):
        self.command = command
        self.name = name
        self.logfile = logfile

        log.msg("LogFileWatcher created to watch %s" % logfile)
        # we are created before the ShellCommand starts. If the logfile we're
        # supposed to be watching already exists, record its size and
        # ctime/mtime so we can tell when it starts to change.
        self.old_logfile_stats = self.statFile()
        self.started = False

        # follow the file, only sending back lines
        # added since we started watching
        self.follow = follow

        # every 2 seconds we check on the file again
        self.poller = task.LoopingCall(self.poll)

    def start(self):
        self.poller.start(self.POLL_INTERVAL).addErrback(self._cleanupPoll)

    def _cleanupPoll(self, err):
        log.err(err, msg="Polling error")
        self.poller = None

    def stop(self):
        self.poll()
        if self.poller is not None:
            self.poller.stop()
        if self.started:
            self.f.close()

    def statFile(self):
        if os.path.exists(self.logfile):
            s = os.stat(self.logfile)
            return (s[ST_CTIME], s[ST_MTIME], s[ST_SIZE])
        return None

    def poll(self):
        if not self.started:
            s = self.statFile()
            if s == self.old_logfile_stats:
                return # not started yet
            if not s:
                # the file was there, but now it's deleted. Forget about the
                # initial state, clearly the process has deleted the logfile
                # in preparation for creating a new one.
                self.old_logfile_stats = None
                return # no file to work with
            self.f = open(self.logfile, "rb")
            # if we only want new lines, seek to
            # where we stat'd so we only find new
            # lines
            if self.follow:
                self.f.seek(s[2], 0)
            self.started = True
        self.f.seek(self.f.tell(), 0)
        while True:
            data = self.f.read(10000)
            if not data:
                return
            self.command.addLogfile(self.name, data)


class ShellCommand:
    # This is a helper class, used by SlaveCommands to run programs in a
    # child shell.

    notreally = False
    BACKUP_TIMEOUT = 5
    KILL = "KILL"
    CHUNK_LIMIT = 128*1024

    # For sending elapsed time:
    startTime = None
    elapsedTime = None
    # I wish we had easy access to CLOCK_MONOTONIC in Python:
    # http://www.opengroup.org/onlinepubs/000095399/functions/clock_getres.html
    # Then changes to the system clock during a run wouldn't effect the "elapsed
    # time" results.

    def __init__(self, builder, command,
                 workdir, environ=None,
                 sendStdout=True, sendStderr=True, sendRC=True,
                 timeout=None, maxTime=None, initialStdin=None,
                 keepStdinOpen=False, keepStdout=False, keepStderr=False,
                 logEnviron=True, logfiles={}, usePTY="slave-config"):
        """

        @param keepStdout: if True, we keep a copy of all the stdout text
                           that we've seen. This copy is available in
                           self.stdout, which can be read after the command
                           has finished.
        @param keepStderr: same, for stderr

        @param usePTY: "slave-config" -> use the SlaveBuilder's usePTY;
            otherwise, true to use a PTY, false to not use a PTY.
        """

        self.builder = builder
        self.command = Obfuscated.get_real(command)
        self.fake_command = Obfuscated.get_fake(command)
        self.sendStdout = sendStdout
        self.sendStderr = sendStderr
        self.sendRC = sendRC
        self.logfiles = logfiles
        self.workdir = workdir
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        self.environ = os.environ.copy()
        if environ:
            if environ.has_key('PYTHONPATH'):
                ppath = environ['PYTHONPATH']
                # Need to do os.pathsep translation.  We could either do that
                # by replacing all incoming ':'s with os.pathsep, or by
                # accepting lists.  I like lists better.
                if not isinstance(ppath, str):
                    # If it's not a string, treat it as a sequence to be
                    # turned in to a string.
                    ppath = os.pathsep.join(ppath)

                if self.environ.has_key('PYTHONPATH'):
                    # special case, prepend the builder's items to the
                    # existing ones. This will break if you send over empty
                    # strings, so don't do that.
                    ppath = ppath + os.pathsep + self.environ['PYTHONPATH']

                environ['PYTHONPATH'] = ppath

            self.environ.update(environ)
        self.initialStdin = initialStdin
        self.keepStdinOpen = keepStdinOpen
        self.logEnviron = logEnviron
        self.timeout = timeout
        self.timer = None
        self.maxTime = maxTime
        self.maxTimer = None
        self.keepStdout = keepStdout
        self.keepStderr = keepStderr


        if usePTY == "slave-config":
            self.usePTY = self.builder.usePTY
        else:
            self.usePTY = usePTY

        # usePTY=True is a convenience for cleaning up all children and
        # grandchildren of a hung command. Fall back to usePTY=False on systems
        # and in situations where ptys cause problems.  PTYs are posix-only,
        # and for .closeStdin to matter, we must use a pipe, not a PTY
        if runtime.platformType != "posix" or initialStdin is not None:
            if self.usePTY and usePTY != "slave-config":
                self.sendStatus({'header': "WARNING: disabling usePTY for this command"})
            self.usePTY = False

        self.logFileWatchers = []
        for name,filevalue in self.logfiles.items():
            filename = filevalue
            follow = False

            # check for a dictionary of options
            # filename is required, others are optional
            if type(filevalue) == dict:
                filename = filevalue['filename']
                follow = filevalue.get('follow', False)

            w = LogFileWatcher(self, name,
                               os.path.join(self.workdir, filename),
                               follow=follow)
            self.logFileWatchers.append(w)

    def __repr__(self):
        return "<slavecommand.ShellCommand '%s'>" % self.fake_command

    def sendStatus(self, status):
        self.builder.sendUpdate(status)

    def start(self):
        # return a Deferred which fires (with the exit code) when the command
        # completes
        if self.keepStdout:
            self.stdout = ""
        if self.keepStderr:
            self.stderr = ""
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
        # ensure workdir exists
        if not os.path.isdir(self.workdir):
            os.makedirs(self.workdir)
        log.msg("ShellCommand._startCommand")
        if self.notreally:
            self.sendStatus({'header': "command '%s' in dir %s" % \
                             (self.fake_command, self.workdir)})
            self.sendStatus({'header': "(not really)\n"})
            self.finished(None, 0)
            return

        self.pp = ShellCommandPP(self)

        if type(self.command) in types.StringTypes:
            if runtime.platformType  == 'win32':
                argv = os.environ['COMSPEC'].split() # allow %COMSPEC% to have args
                if '/c' not in argv: argv += ['/c']
                argv += [self.command]
            else:
                # for posix, use /bin/sh. for other non-posix, well, doesn't
                # hurt to try
                argv = ['/bin/sh', '-c', self.command]
            display = self.fake_command
        else:
            if runtime.platformType  == 'win32' and not self.command[0].lower().endswith(".exe"):
                argv = os.environ['COMSPEC'].split() # allow %COMSPEC% to have args
                if '/c' not in argv: argv += ['/c']
                argv += list(self.command)
            else:
                argv = self.command
            display = " ".join(self.fake_command)

        # $PWD usually indicates the current directory; spawnProcess may not
        # update this value, though, so we set it explicitly here.  This causes
        # weird problems (bug #456) on msys, though..
        if not self.environ.get('MACHTYPE', None) == 'i686-pc-msys':
            self.environ['PWD'] = os.path.abspath(self.workdir)

        # self.stdin is handled in ShellCommandPP.connectionMade

        # first header line is the command in plain text, argv joined with
        # spaces. You should be able to cut-and-paste this into a shell to
        # obtain the same results. If there are spaces in the arguments, too
        # bad.
        log.msg(" " + display)
        self.sendStatus({'header': display+"\n"})

        # then comes the secondary information
        msg = " in dir %s" % (self.workdir,)
        if self.timeout:
            msg += " (timeout %d secs)" % (self.timeout,)
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        msg = " watching logfiles %s" % (self.logfiles,)
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        # then the obfuscated command array for resolving unambiguity
        msg = " argv: %s" % (self.fake_command,)
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        # then the environment, since it sometimes causes problems
        if self.logEnviron:
            msg = " environment:\n"
            env_names = self.environ.keys()
            env_names.sort()
            for name in env_names:
                msg += "  %s=%s\n" % (name, self.environ[name])
            log.msg(" environment: %s" % (self.environ,))
            self.sendStatus({'header': msg})

        if self.initialStdin:
            msg = " writing %d bytes to stdin" % len(self.initialStdin)
            log.msg(" " + msg)
            self.sendStatus({'header': msg+"\n"})

        if self.keepStdinOpen:
            msg = " leaving stdin open"
        else:
            msg = " closing stdin"
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        msg = " using PTY: %s" % bool(self.usePTY)
        log.msg(" " + msg)
        self.sendStatus({'header': msg+"\n"})

        # this will be buffered until connectionMade is called
        if self.initialStdin:
            self.pp.writeStdin(self.initialStdin)
        if not self.keepStdinOpen:
            self.pp.closeStdin()

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
        self.startTime = time.time()

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

        if self.maxTime:
            self.maxTimer = reactor.callLater(self.maxTime, self.doMaxTimeout)

        for w in self.logFileWatchers:
            w.start()


    def _chunkForSend(self, data):
        # limit the chunks that we send over PB to 128k, since it has a
        # hardwired string-size limit of 640k.
        LIMIT = self.CHUNK_LIMIT
        for i in range(0, len(data), LIMIT):
            yield data[i:i+LIMIT]

    def addStdout(self, data):
        if self.sendStdout:
            for chunk in self._chunkForSend(data):
                self.sendStatus({'stdout': chunk})
        if self.keepStdout:
            self.stdout += data
        if self.timer:
            self.timer.reset(self.timeout)

    def addStderr(self, data):
        if self.sendStderr:
            for chunk in self._chunkForSend(data):
                self.sendStatus({'stderr': chunk})
        if self.keepStderr:
            self.stderr += data
        if self.timer:
            self.timer.reset(self.timeout)

    def addLogfile(self, name, data):
        for chunk in self._chunkForSend(data):
            self.sendStatus({'log': (name, chunk)})
        if self.timer:
            self.timer.reset(self.timeout)

    def finished(self, sig, rc):
        self.elapsedTime = time.time() - self.startTime
        log.msg("command finished with signal %s, exit code %s, elapsedTime: %0.6f" % (sig,rc,self.elapsedTime))
        for w in self.logFileWatchers:
             # this will send the final updates
            w.stop()
        if sig is not None:
            rc = -1
        if self.sendRC:
            if sig is not None:
                self.sendStatus(
                    {'header': "process killed by signal %d\n" % sig})
            self.sendStatus({'rc': rc})
        self.sendStatus({'header': "elapsedTime=%0.6f\n" % self.elapsedTime})
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.maxTimer:
            self.maxTimer.cancel()
            self.maxTimer = None
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
        if self.maxTimer:
            self.maxTimer.cancel()
            self.maxTimer = None
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

    def doMaxTimeout(self):
        self.maxTimer = None
        msg = "command timed out: %d seconds elapsed" % self.maxTime
        self.kill(msg)

    def kill(self, msg):
        # This may be called by the timeout, or when the user has decided to
        # abort this build.
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.maxTimer:
            self.maxTimer.cancel()
            self.maxTimer = None
        if hasattr(self.process, "pid") and self.process.pid is not None:
            msg += ", killing pid %s" % self.process.pid
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
                elif not hasattr(self.process, "pid") or self.process.pid is None:
                    log.msg("self.process has no pid")
                else:
                    log.msg("trying os.kill(-pid, %d)" % (sig,))
                    # TODO: maybe use os.killpg instead of a negative pid?
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


    def writeStdin(self, data):
        self.pp.writeStdin(data)

    def closeStdin(self):
        self.pp.closeStdin()


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

    def doStart(self):
        self.running = True
        d = defer.maybeDeferred(self.start)
        d.addBoth(self.commandComplete)
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

    def commandComplete(self, res):
        self.running = False
        return res

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



class SlaveFileUploadCommand(Command):
    """
    Upload a file from slave to build master
    Arguments:

        - ['workdir']:   base directory to use
        - ['slavesrc']:  name of the slave-side file to read from
        - ['writer']:    RemoteReference to a transfer._FileWriter object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
    """
    debug = False

    def setup(self, args):
        self.workdir = args['workdir']
        self.filename = args['slavesrc']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.stderr = None
        self.rc = 0

    def start(self):
        if self.debug:
            log.msg('SlaveFileUploadCommand started')

        # Open file
        self.path = os.path.join(self.builder.basedir,
                                 self.workdir,
                                 os.path.expanduser(self.filename))
        try:
            self.fp = open(self.path, 'rb')
            if self.debug:
                log.msg('Opened %r for upload' % self.path)
        except:
            # TODO: this needs cleanup
            self.fp = None
            self.stderr = 'Cannot open file %r for upload' % self.path
            self.rc = 1
            if self.debug:
                log.msg('Cannot open file %r for upload' % self.path)

        self.sendStatus({'header': "sending %s" % self.path})

        d = defer.Deferred()
        reactor.callLater(0, self._loop, d)
        def _close(res):
            # close the file, but pass through any errors from _loop
            d1 = self.writer.callRemote("close")
            d1.addErrback(log.err)
            d1.addCallback(lambda ignored: res)
            return d1
        d.addBoth(_close)
        d.addBoth(self.finished)
        return d

    def _loop(self, fire_when_done):
        d = defer.maybeDeferred(self._writeBlock)
        def _done(finished):
            if finished:
                fire_when_done.callback(None)
            else:
                self._loop(fire_when_done)
        def _err(why):
            fire_when_done.errback(why)
        d.addCallbacks(_done, _err)
        return None

    def _writeBlock(self):
        """Write a block of data to the remote writer"""

        if self.interrupted or self.fp is None:
            if self.debug:
                log.msg('SlaveFileUploadCommand._writeBlock(): end')
            return True

        length = self.blocksize
        if self.remaining is not None and length > self.remaining:
            length = self.remaining

        if length <= 0:
            if self.stderr is None:
                self.stderr = 'Maximum filesize reached, truncating file %r' \
                                % self.path
                self.rc = 1
            data = ''
        else:
            data = self.fp.read(length)

        if self.debug:
            log.msg('SlaveFileUploadCommand._writeBlock(): '+
                    'allowed=%d readlen=%d' % (length, len(data)))
        if len(data) == 0:
            log.msg("EOF: callRemote(close)")
            return True

        if self.remaining is not None:
            self.remaining = self.remaining - len(data)
            assert self.remaining >= 0
        d = self.writer.callRemote('write', data)
        d.addCallback(lambda res: False)
        return d

    def interrupt(self):
        if self.debug:
            log.msg('interrupted')
        if self.interrupted:
            return
        if self.stderr is None:
            self.stderr = 'Upload of %r interrupted' % self.path
            self.rc = 1
        self.interrupted = True
        # the next _writeBlock call will notice the .interrupted flag

    def finished(self, res):
        if self.debug:
            log.msg('finished: stderr=%r, rc=%r' % (self.stderr, self.rc))
        if self.stderr is None:
            self.sendStatus({'rc': self.rc})
        else:
            self.sendStatus({'stderr': self.stderr, 'rc': self.rc})
        return res

registerSlaveCommand("uploadFile", SlaveFileUploadCommand, command_version)


class SlaveDirectoryUploadCommand(SlaveFileUploadCommand):
    """
    Upload a directory from slave to build master
    Arguments:

        - ['workdir']:   base directory to use
        - ['slavesrc']:  name of the slave-side directory to read from
        - ['writer']:    RemoteReference to a transfer._DirectoryWriter object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
        - ['compress']:  one of [None, 'bz2', 'gz']
    """
    debug = True

    def setup(self, args):
        self.workdir = args['workdir']
        self.dirname = args['slavesrc']
        self.writer = args['writer']
        self.remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.compress = args['compress']
        self.stderr = None
        self.rc = 0

    def start(self):
        if self.debug:
            log.msg('SlaveDirectoryUploadCommand started')

        self.path = os.path.join(self.builder.basedir,
                                 self.workdir,
                                 os.path.expanduser(self.dirname))
        if self.debug:
            log.msg("path: %r" % self.path)

        # Create temporary archive
        fd, self.tarname = tempfile.mkstemp()
        fileobj = os.fdopen(fd, 'w')
        if self.compress == 'bz2':
            mode='w|bz2'
        elif self.compress == 'gz':
            mode='w|gz'
        else:
            mode = 'w'
        archive = tarfile.open(name=self.tarname, mode=mode, fileobj=fileobj)
        archive.add(self.path, '')
        archive.close()
        fileobj.close()

        # Transfer it
        self.fp = open(self.tarname, 'rb')

        self.sendStatus({'header': "sending %s" % self.path})

        d = defer.Deferred()
        reactor.callLater(0, self._loop, d)
        def unpack(res):
            # unpack the archive, but pass through any errors from _loop
            d1 = self.writer.callRemote("unpack")
            d1.addErrback(log.err)
            d1.addCallback(lambda ignored: res)
            return d1
        d.addCallback(unpack)
        d.addBoth(self.finished)
        return d

    def finished(self, res):
        self.fp.close()
        os.remove(self.tarname)
        if self.debug:
            log.msg('finished: stderr=%r, rc=%r' % (self.stderr, self.rc))
        if self.stderr is None:
            self.sendStatus({'rc': self.rc})
        else:
            self.sendStatus({'stderr': self.stderr, 'rc': self.rc})
        return res

registerSlaveCommand("uploadDirectory", SlaveDirectoryUploadCommand, command_version)


class SlaveFileDownloadCommand(Command):
    """
    Download a file from master to slave
    Arguments:

        - ['workdir']:   base directory to use
        - ['slavedest']: name of the slave-side file to be created
        - ['reader']:    RemoteReference to a transfer._FileReader object
        - ['maxsize']:   max size (in bytes) of file to write
        - ['blocksize']: max size for each data block
        - ['mode']:      access mode for the new file
    """
    debug = False

    def setup(self, args):
        self.workdir = args['workdir']
        self.filename = args['slavedest']
        self.reader = args['reader']
        self.bytes_remaining = args['maxsize']
        self.blocksize = args['blocksize']
        self.mode = args['mode']
        self.stderr = None
        self.rc = 0

    def start(self):
        if self.debug:
            log.msg('SlaveFileDownloadCommand starting')

        # Open file
        self.path = os.path.join(self.builder.basedir,
                                 self.workdir,
                                 os.path.expanduser(self.filename))

        dirname = os.path.dirname(self.path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        try:
            self.fp = open(self.path, 'wb')
            if self.debug:
                log.msg('Opened %r for download' % self.path)
            if self.mode is not None:
                # note: there is a brief window during which the new file
                # will have the buildslave's default (umask) mode before we
                # set the new one. Don't use this mode= feature to keep files
                # private: use the buildslave's umask for that instead. (it
                # is possible to call os.umask() before and after the open()
                # call, but cleaning up from exceptions properly is more of a
                # nuisance that way).
                os.chmod(self.path, self.mode)
        except IOError:
            # TODO: this still needs cleanup
            self.fp = None
            self.stderr = 'Cannot open file %r for download' % self.path
            self.rc = 1
            if self.debug:
                log.msg('Cannot open file %r for download' % self.path)

        d = defer.Deferred()
        reactor.callLater(0, self._loop, d)
        def _close(res):
            # close the file, but pass through any errors from _loop
            d1 = self.reader.callRemote('close')
            d1.addErrback(log.err)
            d1.addCallback(lambda ignored: res)
            return d1
        d.addBoth(_close)
        d.addBoth(self.finished)
        return d

    def _loop(self, fire_when_done):
        d = defer.maybeDeferred(self._readBlock)
        def _done(finished):
            if finished:
                fire_when_done.callback(None)
            else:
                self._loop(fire_when_done)
        def _err(why):
            fire_when_done.errback(why)
        d.addCallbacks(_done, _err)
        return None

    def _readBlock(self):
        """Read a block of data from the remote reader."""

        if self.interrupted or self.fp is None:
            if self.debug:
                log.msg('SlaveFileDownloadCommand._readBlock(): end')
            return True

        length = self.blocksize
        if self.bytes_remaining is not None and length > self.bytes_remaining:
            length = self.bytes_remaining

        if length <= 0:
            if self.stderr is None:
                self.stderr = 'Maximum filesize reached, truncating file %r' \
                                % self.path
                self.rc = 1
            return True
        else:
            d = self.reader.callRemote('read', length)
            d.addCallback(self._writeData)
            return d

    def _writeData(self, data):
        if self.debug:
            log.msg('SlaveFileDownloadCommand._readBlock(): readlen=%d' %
                    len(data))
        if len(data) == 0:
            return True

        if self.bytes_remaining is not None:
            self.bytes_remaining = self.bytes_remaining - len(data)
            assert self.bytes_remaining >= 0
        self.fp.write(data)
        return False

    def interrupt(self):
        if self.debug:
            log.msg('interrupted')
        if self.interrupted:
            return
        if self.stderr is None:
            self.stderr = 'Download of %r interrupted' % self.path
            self.rc = 1
        self.interrupted = True
        # now we wait for the next read request to return. _readBlock will
        # abandon the file when it sees self.interrupted set.

    def finished(self, res):
        if self.fp is not None:
            self.fp.close()

        if self.debug:
            log.msg('finished: stderr=%r, rc=%r' % (self.stderr, self.rc))
        if self.stderr is None:
            self.sendStatus({'rc': self.rc})
        else:
            self.sendStatus({'stderr': self.stderr, 'rc': self.rc})
        return res

registerSlaveCommand("downloadFile", SlaveFileDownloadCommand, command_version)



class SlaveShellCommand(Command):
    """This is a Command which runs a shell command. The args dict contains
    the following keys:

        - ['command'] (required): a shell command to run. If this is a string,
                                  it will be run with /bin/sh (['/bin/sh',
                                  '-c', command]). If it is a list
                                  (preferred), it will be used directly.
        - ['workdir'] (required): subdirectory in which the command will be
                                  run, relative to the builder dir
        - ['env']: a dict of environment variables to augment/replace
                   os.environ . PYTHONPATH is treated specially, and
                   should be a list of path components to be prepended to
                   any existing PYTHONPATH environment variable.
        - ['initial_stdin']: a string which will be written to the command's
                             stdin as soon as it starts
        - ['keep_stdin_open']: unless True, the command's stdin will be
                               closed as soon as initial_stdin has been
                               written. Set this to True if you plan to write
                               to stdin after the command has been started.
        - ['want_stdout']: 0 if stdout should be thrown away
        - ['want_stderr']: 0 if stderr should be thrown away
        - ['usePTY']: True or False if the command should use a PTY (defaults to
                      configuration of the slave)
        - ['not_really']: 1 to skip execution and return rc=0
        - ['timeout']: seconds of silence to tolerate before killing command
        - ['maxTime']: seconds before killing command
        - ['logfiles']: dict mapping LogFile name to the workdir-relative
                        filename of a local log file. This local file will be
                        watched just like 'tail -f', and all changes will be
                        written to 'log' status updates.
        - ['logEnviron']: False to not log the environment variables on the slave

    ShellCommand creates the following status messages:
        - {'stdout': data} : when stdout data is available
        - {'stderr': data} : when stderr data is available
        - {'header': data} : when headers (command start/stop) are available
        - {'log': (logfile_name, data)} : when log files have new contents
        - {'rc': rc} : when the process has terminated
    """

    def start(self):
        args = self.args
        # args['workdir'] is relative to Builder directory, and is required.
        assert args['workdir'] is not None
        workdir = os.path.join(self.builder.basedir, args['workdir'])

        c = ShellCommand(self.builder, args['command'],
                         workdir, environ=args.get('env'),
                         timeout=args.get('timeout', None),
                         maxTime=args.get('maxTime', None),
                         sendStdout=args.get('want_stdout', True),
                         sendStderr=args.get('want_stderr', True),
                         sendRC=True,
                         initialStdin=args.get('initial_stdin'),
                         keepStdinOpen=args.get('keep_stdin_open'),
                         logfiles=args.get('logfiles', {}),
                         usePTY=args.get('usePTY', "slave-config"),
                         logEnviron=args.get('logEnviron', True),
                         )
        self.command = c
        d = self.command.start()
        return d

    def interrupt(self):
        self.interrupted = True
        self.command.kill("command interrupted")

    def writeStdin(self, data):
        self.command.writeStdin(data)

    def closeStdin(self):
        self.command.closeStdin()

registerSlaveCommand("shell", SlaveShellCommand, command_version)


class DummyCommand(Command):
    """
    I am a dummy no-op command that by default takes 5 seconds to complete.
    See L{buildbot.steps.dummy.RemoteDummy}
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

registerSlaveCommand("dummy", DummyCommand, command_version)


# this maps handle names to a callable. When the WaitCommand starts, this
# callable is invoked with no arguments. It should return a Deferred. When
# that Deferred fires, our WaitCommand will finish.
waitCommandRegistry = {}

class WaitCommand(Command):
    """
    I am a dummy command used by the buildbot unit test suite. I want for the
    unit test to tell us to finish. See L{buildbot.steps.dummy.Wait}
    """

    def start(self):
        self.d = defer.Deferred()
        log.msg("  starting wait command [%s]" % self.stepId)
        handle = self.args['handle']
        cb = waitCommandRegistry[handle]
        del waitCommandRegistry[handle]
        def _called():
            log.msg(" wait-%s starting" % (handle,))
            d = cb()
            def _done(res):
                log.msg(" wait-%s finishing: %s" % (handle, res))
                return res
            d.addBoth(_done)
            d.addCallbacks(self.finished, self.failed)
        reactor.callLater(0, _called)
        return self.d

    def interrupt(self):
        log.msg("  wait command interrupted")
        if self.interrupted:
            return
        self.interrupted = True
        self.finished("interrupted")

    def finished(self, res):
        log.msg("  wait command finished [%s]" % self.stepId)
        if self.interrupted:
            self.sendStatus({'rc': 2})
        else:
            self.sendStatus({'rc': 0})
        self.d.callback(0)
    def failed(self, why):
        log.msg("  wait command failed [%s]" % self.stepId)
        self.sendStatus({'rc': 1})
        self.d.callback(0)

registerSlaveCommand("dummy.wait", WaitCommand, command_version)


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

        - ['maxTime']:  seconds before we kill off the command

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
        self.env['LC_MESSAGES'] = "C"

        self.workdir = args['workdir']
        self.mode = args.get('mode', "update")
        self.revision = args.get('revision')
        self.patch = args.get('patch')
        self.timeout = args.get('timeout', 120)
        self.maxTime = args.get('maxTime', None)
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
        self.maybeClobber(d)
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

    def maybeClobber(self, d):
        # do we need to clobber anything?
        if self.mode in ("copy", "clobber", "export"):
            d.addCallback(self.doClobber, self.workdir)

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
            olddata = self.readSourcedata()
            if olddata != self.sourcedata:
                return False
        except IOError:
            return False
        return True

    def sourcedirIsPatched(self):
        return os.path.exists(os.path.join(self.builder.basedir,
                                           self.workdir,
                                           ".buildbot-patched"))

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

    def readSourcedata(self):
        return open(self.sourcedatafile, "r").read()

    def writeSourcedata(self, res):
        open(self.sourcedatafile, "w").write(self.sourcedata)
        return res

    def sourcedirIsUpdateable(self):
        """Returns True if the tree can be updated."""
        raise NotImplementedError("this must be implemented in a subclass")

    def doVCUpdate(self):
        """Returns a deferred with the steps to update a checkout."""
        raise NotImplementedError("this must be implemented in a subclass")

    def doVCFull(self):
        """Returns a deferred with the steps to do a fresh checkout."""
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
                self.maybeClobber(d)
                d.addCallback(lambda res: self.doVCFull())
                d.addBoth(self.maybeDoVCRetry)
                reactor.callLater(delay, d.callback, None)
                return d
        return res

    def doClobber(self, dummy, dirname, chmodDone=False):
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
                         sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                         usePTY=False)

        self.command = c
        # sendRC=0 means the rm command will send stdout/stderr to the
        # master, but not the rc=0 when it finishes. That job is left to
        # _sendRC
        d = c.start()
        # The rm -rf may fail if there is a left-over subdir with chmod 000
        # permissions. So if we get a failure, we attempt to chmod suitable
        # permissions and re-try the rm -rf.
        if chmodDone:
            d.addCallback(self._abandonOnFailure)
        else:
            d.addCallback(lambda rc: self.doClobberTryChmodIfFail(rc, dirname))
        return d

    def doClobberTryChmodIfFail(self, rc, dirname):
        assert isinstance(rc, int)
        if rc == 0:
            return defer.succeed(0)
        # Attempt a recursive chmod and re-try the rm -rf after.
        command = ["chmod", "-R", "u+rwx", os.path.join(self.builder.basedir, dirname)]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                         usePTY=False)

        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        d.addCallback(lambda dummy: self.doClobber(dummy, dirname, True))
        return d

    def doCopy(self, res):
        # now copy tree to workdir
        fromdir = os.path.join(self.builder.basedir, self.srcdir)
        todir = os.path.join(self.builder.basedir, self.workdir)
        if runtime.platformType != "posix":
            self.sendStatus({'header': "Since we're on a non-POSIX platform, "
            "we're not going to try to execute cp in a subprocess, but instead "
            "use shutil.copytree(), which will block until it is complete.  "
            "fromdir: %s, todir: %s\n" % (fromdir, todir)})
            shutil.copytree(fromdir, todir)
            return defer.succeed(0)

        if not os.path.exists(os.path.dirname(todir)):
            os.makedirs(os.path.dirname(todir))
        if os.path.exists(todir):
            # I don't think this happens, but just in case..
            log.msg("cp target '%s' already exists -- cp will not do what you think!" % todir)

        command = ['cp', '-R', '-P', '-p', fromdir, todir]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout, maxTime=self.maxTime,
                         usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d

    def doPatch(self, res):
        patchlevel = self.patch[0]
        diff = self.patch[1]
        root = None
        if len(self.patch) >= 3:
            root = self.patch[2]
        command = [
            getCommand("patch"),
            '-p%d' % patchlevel,
            '--remove-empty-files',
            '--force',
            '--forward',
        ]
        dir = os.path.join(self.builder.basedir, self.workdir)
        # Mark the directory so we don't try to update it later, or at least try
        # to revert first.
        marker = open(os.path.join(dir, ".buildbot-patched"), "w")
        marker.write("patched\n")
        marker.close()

        # Update 'dir' with the 'root' option. Make sure it is a subdirectory
        # of dir.
        if (root and
            os.path.abspath(os.path.join(dir, root)
                            ).startswith(os.path.abspath(dir))):
            dir = os.path.join(dir, root)

        # now apply the patch
        c = ShellCommand(self.builder, command, dir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, initialStdin=diff, usePTY=False)
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
    ['checkout_options']: a list of strings to use after checkout,
                          but before revision and branch specifiers
    """

    header = "cvs operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("cvs")
        self.cvsroot = args['cvsroot']
        self.cvsmodule = args['cvsmodule']
        self.global_options = args.get('global_options', [])
        self.checkout_options = args.get('checkout_options', [])
        self.branch = args.get('branch')
        self.login = args.get('login')
        self.sourcedata = "%s\n%s\n%s\n" % (self.cvsroot, self.cvsmodule,
                                            self.branch)

    def sourcedirIsUpdateable(self):
        return (not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir, "CVS")))

    def start(self):
        if self.login is not None:
            # need to do a 'cvs login' command first
            d = self.builder.basedir
            command = ([self.vcexe, '-d', self.cvsroot] + self.global_options
                       + ['login'])
            c = ShellCommand(self.builder, command, d,
                             sendRC=False, timeout=self.timeout,
                             maxTime=self.maxTime,
                             initialStdin=self.login+"\n", usePTY=False)
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
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
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

        if verb == "checkout":
            command += self.checkout_options
        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        command += [self.cvsmodule]

        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def parseGotRevision(self):
        # CVS does not have any kind of revision stamp to speak of. We return
        # the current timestamp as a best-effort guess, but this depends upon
        # the local system having a clock that is
        # reasonably-well-synchronized with the repository.
        return time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime())

registerSlaveCommand("cvs", CVS, command_version)

class SVN(SourceBase):
    """Subversion-specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['svnurl'] (required): the SVN repository string
    ['username']:          Username passed to the svn command
    ['password']:          Password passed to the svn command
    ['keep_on_purge']:     Files and directories to keep between updates
    ['ignore_ignores']:    Ignore ignores when purging changes
    ['always_purge']:      Always purge local changes after each build
    ['depth']:     	   Pass depth argument to subversion 1.5+ 
    """

    header = "svn operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("svn")
        self.svnurl = args['svnurl']
        self.sourcedata = "%s\n" % self.svnurl
        self.keep_on_purge = args.get('keep_on_purge', [])
        self.keep_on_purge.append(".buildbot-sourcedata")
        self.ignore_ignores = args.get('ignore_ignores', True)
        self.always_purge = args.get('always_purge', False)

        self.svn_args = []
        if args.has_key('username'):
            self.svn_args.extend(["--username", args['username']])
        if args.has_key('password'):
            self.svn_args.extend(["--password", Obfuscated(args['password'], "XXXX")])
        if args.get('extra_args', None) is not None:
            self.svn_args.extend(args['extra_args'])

	if args.has_key('depth'):
	    self.svn_args.extend(["--depth",args['depth']])

    def _dovccmd(self, command, args, rootdir=None, cb=None, **kwargs):
        if rootdir is None:
            rootdir = os.path.join(self.builder.basedir, self.srcdir)
        fullCmd = [self.vcexe, command, '--non-interactive', '--no-auth-cache']
        fullCmd.extend(self.svn_args)
        fullCmd.extend(args)
        c = ShellCommand(self.builder, fullCmd, rootdir,
                         environ=self.env, sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False, **kwargs)
        self.command = c
        d = c.start()
        if cb:
            d.addCallback(self._abandonOnFailure)
            d.addCallback(cb)
        return d

    def sourcedirIsUpdateable(self):
        return os.path.isdir(os.path.join(self.builder.basedir,
                                          self.srcdir, ".svn"))

    def doVCUpdate(self):
        if self.sourcedirIsPatched() or self.always_purge:
            return self._purgeAndUpdate()
        revision = self.args['revision'] or 'HEAD'
        # update: possible for mode in ('copy', 'update')
        return self._dovccmd('update', ['--revision', str(revision)],
                             keepStdout=True)

    def doVCFull(self):
        revision = self.args['revision'] or 'HEAD'
        args = ['--revision', str(revision), self.svnurl, self.srcdir]
        if self.mode == "export":
            command = 'export'
        else:
            # mode=='clobber', or copy/update on a broken workspace
            command = 'checkout'
        return self._dovccmd(command, args, rootdir=self.builder.basedir,
                             keepStdout=True)

    def _purgeAndUpdate(self):
        """svn revert has several corner cases that make it unpractical.

        Use the Force instead and delete everything that shows up in status."""
        args = ['--xml']
        if self.ignore_ignores:
          args.append('--no-ignore')
        return self._dovccmd('status', args, keepStdout=True, sendStdout=False,
                             cb=self._purgeAndUpdate2)

    def _purgeAndUpdate2(self, res):
        """Delete everything that shown up on status."""
        result_xml = parseString(self.command.stdout)
        for entry in result_xml.getElementsByTagName('entry'):
            filename = entry.getAttribute('path')
            if filename in self.keep_on_purge:
                continue
            filepath = os.path.join(self.builder.basedir, self.workdir,
                                    filename)
            self.sendStatus({'stdout': "%s\n" % filepath})
            if os.path.isfile(filepath):
                os.chmod(filepath, 0700)
                os.remove(filepath)
            else:
                rmdirRecursive(filepath)
        # Now safe to update.
        revision = self.args['revision'] or 'HEAD'
        return self._dovccmd('update', ['--revision', str(revision)],
                             keepStdout=True)

    def getSvnVersionCommand(self):
        """
        Get the (shell) command used to determine SVN revision number
        of checked-out code

        return: list of strings, passable as the command argument to ShellCommand
        """
        # svn checkout operations finish with 'Checked out revision 16657.'
        # svn update operations finish the line 'At revision 16654.'
        # But we don't use those. Instead, run 'svnversion'.
        svnversion_command = getCommand("svnversion")
        # older versions of 'svnversion' (1.1.4) require the WC_PATH
        # argument, newer ones (1.3.1) do not.
        return [svnversion_command, "."]

    def parseGotRevision(self):
        c = ShellCommand(self.builder,
                         self.getSvnVersionCommand(),
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            r_raw = c.stdout.strip()
            # Extract revision from the version "number" string
            r = r_raw.rstrip('MS')
            r = r.split(':')[-1]
            got_version = None
            try:
                got_version = int(r)
            except ValueError:
                msg =("SVN.parseGotRevision unable to parse output "
                      "of svnversion: '%s'" % r_raw)
                log.msg(msg)
                self.sendStatus({'header': msg + "\n"})
            return got_version
        d.addCallback(_parse)
        return d


registerSlaveCommand("svn", SVN, command_version)

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
        # checking out a specific revision requires a full 'darcs get'
        return (not self.revision and
                not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir, "_darcs")))

    def doVCUpdate(self):
        assert not self.revision
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'pull', '--all', '--verbose']
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
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
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
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
                         keepStdout=True, usePTY=False)
        d = c.start()
        d.addCallback(lambda res: c.stdout)
        return d

registerSlaveCommand("darcs", Darcs, command_version)

class Monotone(SourceBase):
    """Monotone-specific VC operation.  In addition to the arguments handled
    by SourceBase, this command reads the following keys:

    ['server_addr'] (required): the address of the server to pull from
    ['branch'] (required): the branch the revision is on
    ['db_path'] (required): the local database path to use
    ['revision'] (required): the revision to check out
    ['monotone']: (required): path to monotone executable
    """

    header = "monotone operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.server_addr = args["server_addr"]
        self.branch = args["branch"]
        self.db_path = args["db_path"]
        self.revision = args["revision"]
        self.monotone = args["monotone"]
        self._made_fulls = False
        self._pull_timeout = args["timeout"]

    def _makefulls(self):
        if not self._made_fulls:
            basedir = self.builder.basedir
            self.full_db_path = os.path.join(basedir, self.db_path)
            self.full_srcdir = os.path.join(basedir, self.srcdir)
            self._made_fulls = True

    def sourcedirIsUpdateable(self):
        self._makefulls()
        return (not self.sourcedirIsPatched() and
                os.path.isfile(self.full_db_path) and
                os.path.isdir(os.path.join(self.full_srcdir, "MT")))

    def doVCUpdate(self):
        return self._withFreshDb(self._doUpdate)

    def _doUpdate(self):
        # update: possible for mode in ('copy', 'update')
        command = [self.monotone, "update",
                   "-r", self.revision,
                   "-b", self.branch]
        c = ShellCommand(self.builder, command, self.full_srcdir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        return self._withFreshDb(self._doFull)

    def _doFull(self):
        command = [self.monotone, "--db=" + self.full_db_path,
                   "checkout",
                   "-r", self.revision,
                   "-b", self.branch,
                   self.full_srcdir]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def _withFreshDb(self, callback):
        self._makefulls()
        # first ensure the db exists and is usable
        if os.path.isfile(self.full_db_path):
            # already exists, so run 'db migrate' in case monotone has been
            # upgraded under us
            command = [self.monotone, "db", "migrate",
                       "--db=" + self.full_db_path]
        else:
            # We'll be doing an initial pull, so up the timeout to 3 hours to
            # make sure it will have time to complete.
            self._pull_timeout = max(self._pull_timeout, 3 * 60 * 60)
            self.sendStatus({"header": "creating database %s\n"
                                       % (self.full_db_path,)})
            command = [self.monotone, "db", "init",
                       "--db=" + self.full_db_path]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        d.addCallback(self._didDbInit)
        d.addCallback(self._didPull, callback)
        return d

    def _didDbInit(self, res):
        command = [self.monotone, "--db=" + self.full_db_path,
                   "pull", "--ticker=dot", self.server_addr, self.branch]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self._pull_timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.sendStatus({"header": "pulling %s from %s\n"
                                   % (self.branch, self.server_addr)})
        self.command = c
        return c.start()

    def _didPull(self, res, callback):
        return callback()

registerSlaveCommand("monotone", Monotone, command_version)


class Git(SourceBase):
    """Git specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['repourl'] (required):    the upstream GIT repository string
    ['branch'] (optional):     which version (i.e. branch or tag) to
                               retrieve. Default: "master".
    ['submodules'] (optional): whether to initialize and update
                               submodules. Default: False.
    ['ignore_ignores']:        ignore ignores when purging changes.
    """

    header = "git operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("git")
        self.repourl = args['repourl']
        self.branch = args.get('branch')
        if not self.branch:
            self.branch = "master"
        self.sourcedata = "%s %s\n" % (self.repourl, self.branch)
        self.submodules = args.get('submodules')
        self.ignore_ignores = args.get('ignore_ignores', True)

    def _fullSrcdir(self):
        return os.path.join(self.builder.basedir, self.srcdir)

    def _commitSpec(self):
        if self.revision:
            return self.revision
        return self.branch

    def sourcedirIsUpdateable(self):
        return os.path.isdir(os.path.join(self._fullSrcdir(), ".git"))

    def _dovccmd(self, command, cb=None, **kwargs):
        c = ShellCommand(self.builder, [self.vcexe] + command, self._fullSrcdir(),
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False, **kwargs)
        self.command = c
        d = c.start()
        if cb:
            d.addCallback(self._abandonOnFailure)
            d.addCallback(cb)
        return d

    # If the repourl matches the sourcedata file, then
    # we can say that the sourcedata matches.  We can
    # ignore branch changes, since Git can work with
    # many branches fetched, and we deal with it properly
    # in doVCUpdate.
    def sourcedataMatches(self):
        try:
            olddata = self.readSourcedata()
            if not olddata.startswith(self.repourl+' '):
                return False
        except IOError:
            return False
        return True

    def _cleanSubmodules(self, res):
        command = ['submodule', 'foreach', 'git', 'clean', '-d', '-f']
        if self.ignore_ignores:
            command.append('-x')
        return self._dovccmd(command)

    def _updateSubmodules(self, res):
        return self._dovccmd(['submodule', 'update'], self._cleanSubmodules)

    def _initSubmodules(self, res):
        if self.submodules:
            return self._dovccmd(['submodule', 'init'], self._updateSubmodules)
        else:
            return defer.succeed(0)

    def _didHeadCheckout(self, res):
        # Rename branch, so that the repo will have the expected branch name
        # For further information about this, see the commit message
        command = ['branch', '-M', self.branch]
        return self._dovccmd(command, self._initSubmodules)
        
    def _didFetch(self, res):
        if self.revision:
            head = self.revision
        else:
            head = 'FETCH_HEAD'

        # That is not sufficient. git will leave unversioned files and empty
        # directories. Clean them up manually in _didReset.
        command = ['reset', '--hard', head]
        return self._dovccmd(command, self._didHeadCheckout)

    # Update first runs "git clean", removing local changes,
    # if the branch to be checked out has changed.  This, combined
    # with the later "git reset" equates clobbering the repo,
    # but it's much more efficient.
    def doVCUpdate(self):
        try:
            # Check to see if our branch has changed
            diffbranch = self.sourcedata != self.readSourcedata()
        except IOError:
            diffbranch = False
        if diffbranch:
            command = ['git', 'clean', '-f', '-d']
            if self.ignore_ignores:
                command.append('-x')
            c = ShellCommand(self.builder, command, self._fullSrcdir(),
                             sendRC=False, timeout=self.timeout, usePTY=False)
            self.command = c
            d = c.start()
            d.addCallback(self._abandonOnFailure)
            d.addCallback(self._didClean)
            return d
        return self._didClean(None)

    def _doFetch(self, dummy):
        # The plus will make sure the repo is moved to the branch's
        # head even if it is not a simple "fast-forward"
        command = ['fetch', '-t', self.repourl, '+%s' % self.branch]
        self.sendStatus({"header": "fetching branch %s from %s\n"
                                        % (self.branch, self.repourl)})
        return self._dovccmd(command, self._didFetch)

    def _didClean(self, dummy):
        # After a clean, try to use the given revision if we have one.
        if self.revision:
            # We know what revision we want.  See if we have it.
            d = self._dovccmd(['reset', '--hard', self.revision],
                              self._initSubmodules)
            # If we are unable to reset to the specified version, we
            # must do a fetch first and retry.
            d.addErrback(self._doFetch)
            return d
        else:
            # No known revision, go grab the latest.
            return self._doFetch(None)

    def _didInit(self, res):
        return self.doVCUpdate()

    def doVCFull(self):
        os.makedirs(self._fullSrcdir())
        return self._dovccmd(['init'], self._didInit)

    def parseGotRevision(self):
        command = ['rev-parse', 'HEAD']
        def _parse(res):
            hash = self.command.stdout.strip()
            if len(hash) != 40:
                return None
            return hash
        return self._dovccmd(command, _parse, keepStdout=True)

registerSlaveCommand("git", Git, command_version)

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
        # Arch cannot roll a directory backwards, so if they ask for a
        # specific revision, clobber the directory. Technically this
        # could be limited to the cases where the requested revision is
        # later than our current one, but it's too hard to extract the
        # current revision from the tree.
        return (not self.revision and
                not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir, "{arch}")))

    def doVCUpdate(self):
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'replay']
        if self.revision:
            command.append(self.revision)
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        # to do a checkout, we must first "register" the archive by giving
        # the URL to tla, which will go to the repository at that URL and
        # figure out the archive name. tla will tell you the archive name
        # when it is done, and all further actions must refer to this name.

        command = [self.vcexe, 'register-archive', '--force', self.url]
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, keepStdout=True, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
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
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
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
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
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
                         keepStdout=True, usePTY=False)
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

registerSlaveCommand("arch", Arch, command_version)

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
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
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
                         keepStdout=True, usePTY=False)
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

registerSlaveCommand("bazaar", Bazaar, command_version)


class Bzr(SourceBase):
    """bzr-specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['repourl'] (required): the Bzr repository string
    """

    header = "bzr operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("bzr")
        self.repourl = args['repourl']
        self.sourcedata = "%s\n" % self.repourl
        self.revision = self.args.get('revision')
        self.forceSharedRepo = args.get('forceSharedRepo')

    def sourcedirIsUpdateable(self):
        # checking out a specific revision requires a full 'bzr checkout'
        return (not self.revision and
                not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir, ".bzr")))

    def start(self):
        def cont(res):
            # Continue with start() method in superclass.
            return SourceBase.start(self)

        if self.forceSharedRepo:
            d = self.doForceSharedRepo();
            d.addCallback(cont)
            return d
        else:
            return cont(None)

    def doVCUpdate(self):
        assert not self.revision
        # update: possible for mode in ('copy', 'update')
        srcdir = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'update']
        c = ShellCommand(self.builder, command, srcdir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        # checkout or export
        d = self.builder.basedir
        if self.mode == "export":
            # exporting in bzr requires a separate directory
            return self.doVCExport()
        # originally I added --lightweight here, but then 'bzr revno' is
        # wrong. The revno reported in 'bzr version-info' is correct,
        # however. Maybe this is a bzr bug?
        #
        # In addition, you cannot perform a 'bzr update' on a repo pulled
        # from an HTTP repository that used 'bzr checkout --lightweight'. You
        # get a "ERROR: Cannot lock: transport is read only" when you try.
        #
        # So I won't bother using --lightweight for now.

        command = [self.vcexe, 'checkout']
        if self.revision:
            command.append('--revision')
            command.append(str(self.revision))
        command.append(self.repourl)
        command.append(self.srcdir)

        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        return d

    def doVCExport(self):
        tmpdir = os.path.join(self.builder.basedir, "export-temp")
        srcdir = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'checkout', '--lightweight']
        if self.revision:
            command.append('--revision')
            command.append(str(self.revision))
        command.append(self.repourl)
        command.append(tmpdir)
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        def _export(res):
            command = [self.vcexe, 'export', srcdir]
            c = ShellCommand(self.builder, command, tmpdir,
                             sendRC=False, timeout=self.timeout,
                             maxTime=self.maxTime, usePTY=False)
            self.command = c
            return c.start()
        d.addCallback(_export)
        return d

    def doForceSharedRepo(self):
        # Don't send stderr. When there is no shared repo, this might confuse
        # users, as they will see a bzr error message. But having no shared
        # repo is not an error, just an indication that we need to make one.
        c = ShellCommand(self.builder, [self.vcexe, 'info', '.'],
                         self.builder.basedir,
                         sendStderr=False, sendRC=False, usePTY=False)
        d = c.start()
        def afterCheckSharedRepo(res):
            if type(res) is int and res != 0:
                log.msg("No shared repo found, creating it")
                # bzr info fails, try to create shared repo.
                c = ShellCommand(self.builder, [self.vcexe, 'init-repo', '.'],
                                 self.builder.basedir,
                                 sendRC=False, usePTY=False)
                self.command = c
                return c.start()
            else:
                return defer.succeed(res)
        d.addCallback(afterCheckSharedRepo)
        return d

    def get_revision_number(self, out):
        # it feels like 'bzr revno' sometimes gives different results than
        # the 'revno:' line from 'bzr version-info', and the one from
        # version-info is more likely to be correct.
        for line in out.split("\n"):
            colon = line.find(":")
            if colon != -1:
                key, value = line[:colon], line[colon+2:]
                if key == "revno":
                    return int(value)
        raise ValueError("unable to find revno: in bzr output: '%s'" % out)

    def parseGotRevision(self):
        command = [self.vcexe, "version-info"]
        c = ShellCommand(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            try:
                return self.get_revision_number(c.stdout)
            except ValueError:
                msg =("Bzr.parseGotRevision unable to parse output "
                      "of bzr version-info: '%s'" % c.stdout.strip())
                log.msg(msg)
                self.sendStatus({'header': msg + "\n"})
                return None
        d.addCallback(_parse)
        return d

registerSlaveCommand("bzr", Bzr, command_version)

class Mercurial(SourceBase):
    """Mercurial specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['repourl'] (required): the Mercurial repository string
    ['clobberOnBranchChange']: Document me. See ticket #462.
    """

    header = "mercurial operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("hg")
        self.repourl = args['repourl']
        self.clobberOnBranchChange = args.get('clobberOnBranchChange', True)
        self.sourcedata = "%s\n" % self.repourl
        self.branchType = args.get('branchType', 'dirname')
        self.stdout = ""
        self.stderr = ""

    def sourcedirIsUpdateable(self):
        return os.path.isdir(os.path.join(self.builder.basedir,
                                          self.srcdir, ".hg"))

    def doVCUpdate(self):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'pull', '--verbose', self.repourl]
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, keepStdout=True, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._handleEmptyUpdate)
        d.addCallback(self._update)
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
        command = [self.vcexe, 'clone', '--verbose', '--noupdate']

        # if got revision, clobbering and in dirname, only clone to specific revision
        # (otherwise, do full clone to re-use .hg dir for subsequent builds)
        if self.args.get('revision') and self.mode == 'clobber' and self.branchType == 'dirname':
            command.extend(['--rev', self.args.get('revision')])
        command.extend([self.repourl, d])

        c = ShellCommand(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        cmd1 = c.start()
        cmd1.addCallback(self._update)
        return cmd1

    def _clobber(self, dummy, dirname):
        def _vcfull(res):
            return self.doVCFull()

        c = self.doClobber(dummy, dirname)
        c.addCallback(_vcfull)

        return c

    def _purge(self, dummy, dirname):
        d = os.path.join(self.builder.basedir, self.srcdir)
        purge = [self.vcexe, 'purge', '--all']
        purgeCmd = ShellCommand(self.builder, purge, d,
                                sendStdout=False, sendStderr=False,
                                keepStdout=True, keepStderr=True, usePTY=False)

        def _clobber(res):
            if res != 0:
                # purge failed, we need to switch to a classic clobber
                msg = "'hg purge' failed: %s\n%s. Clobbering." % (purgeCmd.stdout, purgeCmd.stderr)
                self.sendStatus({'header': msg + "\n"})
                log.msg(msg)

                return self._clobber(dummy, dirname)

            # Purge was a success, then we need to update
            return self._update2(res)

        p = purgeCmd.start()
        p.addCallback(_clobber)
        return p

    def _update(self, res):
        if res != 0:
            return res

        # compare current branch to update
        self.update_branch = self.args.get('branch',  'default')

        d = os.path.join(self.builder.basedir, self.srcdir)
        parentscmd = [self.vcexe, 'identify', '--num', '--branch']
        cmd = ShellCommand(self.builder, parentscmd, d,
                           sendStdout=False, sendStderr=False,
                           keepStdout=True, keepStderr=True, usePTY=False)

        self.clobber = None

        def _parseIdentify(res):
            if res != 0:
                msg = "'hg identify' failed: %s\n%s" % (cmd.stdout, cmd.stderr)
                self.sendStatus({'header': msg + "\n"})
                log.msg(msg)
                return res

            log.msg('Output: %s' % cmd.stdout)

            match = re.search(r'^(.+) (.+)$', cmd.stdout)
            assert match

            rev = match.group(1)
            current_branch = match.group(2)

            if rev == '-1':
                msg = "Fresh hg repo, don't worry about in-repo branch name"
                log.msg(msg)

            elif self.sourcedirIsPatched():
                self.clobber = self._purge

            elif self.update_branch != current_branch:
                msg = "Working dir is on in-repo branch '%s' and build needs '%s'." % (current_branch, self.update_branch)
                if self.clobberOnBranchChange:
                    msg += ' Cloberring.'
                else:
                    msg += ' Updating.'

                self.sendStatus({'header': msg + "\n"})
                log.msg(msg)

                # Clobbers only if clobberOnBranchChange is set
                if self.clobberOnBranchChange:
                    self.clobber = self._purge

            else:
                msg = "Working dir on same in-repo branch as build (%s)." % (current_branch)
                log.msg(msg)

            return 0

        def _checkRepoURL(res):
            parentscmd = [self.vcexe, 'paths', 'default']
            cmd2 = ShellCommand(self.builder, parentscmd, d,
                               sendStdout=False, sendStderr=False,
                               keepStdout=True, keepStderr=True, usePTY=False)

            def _parseRepoURL(res):
                if res == 1:
                    if "not found!" == cmd2.stderr.strip():
                        msg = "hg default path not set. Not checking repo url for clobber test"
                        log.msg(msg)
                        return 0
                    else:
                        msg = "'hg paths default' failed: %s\n%s" % (cmd2.stdout, cmd2.stderr)
                        log.msg(msg)
                        return 1

                oldurl = cmd2.stdout.strip()

                log.msg("Repo cloned from: '%s'" % oldurl)

                if sys.platform == "win32":
                    oldurl = oldurl.lower().replace('\\', '/')
                    repourl = self.repourl.lower().replace('\\', '/')
                    if repourl.startswith('file://'):
                        repourl = repourl.split('file://')[1]
                else:
                    repourl = self.repourl

                oldurl = remove_userpassword(oldurl)
                repourl = remove_userpassword(repourl)

                if oldurl != repourl:
                    self.clobber = self._clobber
                    msg = "RepoURL changed from '%s' in wc to '%s' in update. Clobbering" % (oldurl, repourl)
                    log.msg(msg)

                return 0

            c = cmd2.start()
            c.addCallback(_parseRepoURL)
            return c

        def _maybeClobber(res):
            if self.clobber:
                msg = "Clobber flag set. Doing clobbering"
                log.msg(msg)

                def _vcfull(res):
                    return self.doVCFull()

                return self.clobber(None, self.srcdir)

            return 0

        c = cmd.start()
        c.addCallback(_parseIdentify)
        c.addCallback(_checkRepoURL)
        c.addCallback(_maybeClobber)
        c.addCallback(self._update2)
        return c

    def _update2(self, res):
        d = os.path.join(self.builder.basedir, self.srcdir)

        updatecmd=[self.vcexe, 'update', '--clean', '--repository', d]
        if self.args.get('revision'):
            updatecmd.extend(['--rev', self.args['revision']])
        else:
            updatecmd.extend(['--rev', self.args.get('branch',  'default')])
        self.command = ShellCommand(self.builder, updatecmd,
            self.builder.basedir, sendRC=False,
            timeout=self.timeout, maxTime=self.maxTime, usePTY=False)
        return self.command.start()

    def parseGotRevision(self):
        # we use 'hg identify' to find out what we wound up with
        command = [self.vcexe, "identify"]
        c = ShellCommand(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            m = re.search(r'^(\w+)', c.stdout)
            return m.group(1)
        d.addCallback(_parse)
        return d

registerSlaveCommand("hg", Mercurial, command_version)


class P4Base(SourceBase):
    """Base class for P4 source-updaters

    ['p4port'] (required): host:port for server to access
    ['p4user'] (optional): user to use for access
    ['p4passwd'] (optional): passwd to try for the user
    ['p4client'] (optional): client spec to use
    """
    def setup(self, args):
        SourceBase.setup(self, args)
        self.p4port = args['p4port']
        self.p4client = args['p4client']
        self.p4user = args['p4user']
        self.p4passwd = args['p4passwd']

    def parseGotRevision(self):
        # Executes a p4 command that will give us the latest changelist number
        # of any file under the current (or default) client:
        command = ['p4']
        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            command.extend(['-P', self.p4passwd])
        if self.p4client:
            command.extend(['-c', self.p4client])
        # add '-s submitted' for bug #626
        command.extend(['changes', '-s', 'submitted', '-m', '1', '#have'])
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         environ=self.env, timeout=self.timeout,
                         maxTime=self.maxTime, sendStdout=True,
                         sendStderr=False, sendRC=False, keepStdout=True,
                         usePTY=False)
        self.command = c
        d = c.start()

        def _parse(res):
            # 'p4 -c clien-name change -m 1 "#have"' will produce an output like:
            # "Change 28147 on 2008/04/07 by p4user@hostname..."
            # The number after "Change" is the one we want.
            m = re.match('Change\s+(\d+)\s+', c.stdout)
            if m:
                return m.group(1)
            return None
        d.addCallback(_parse)
        return d


class P4(P4Base):
    """A P4 source-updater.

    ['p4port'] (required): host:port for server to access
    ['p4user'] (optional): user to use for access
    ['p4passwd'] (optional): passwd to try for the user
    ['p4client'] (optional): client spec to use
    ['p4extra_views'] (optional): additional client views to use
    """

    header = "p4"

    def setup(self, args):
        P4Base.setup(self, args)
        self.p4base = args['p4base']
        self.p4extra_views = args['p4extra_views']
        self.p4mode = args['mode']
        self.p4branch = args['branch']

        self.sourcedata = str([
            # Perforce server.
            self.p4port,

            # Client spec.
            self.p4client,

            # Depot side of view spec.
            self.p4base,
            self.p4branch,
            self.p4extra_views,

            # Local side of view spec (srcdir is made from these).
            self.builder.basedir,
            self.mode,
            self.workdir
        ])


    def sourcedirIsUpdateable(self):
        # We assume our client spec is still around.
        # We just say we aren't updateable if the dir doesn't exist so we
        # don't get ENOENT checking the sourcedata.
        return (not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir)))

    def doVCUpdate(self):
        return self._doP4Sync(force=False)

    def _doP4Sync(self, force):
        command = ['p4']

        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            command.extend(['-P', self.p4passwd])
        if self.p4client:
            command.extend(['-c', self.p4client])
        command.extend(['sync'])
        if force:
            command.extend(['-f'])
        if self.revision:
            command.extend(['@' + str(self.revision)])
        env = {}
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         environ=env, sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, keepStdout=True, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d


    def doVCFull(self):
        env = {}
        command = ['p4']
        client_spec = ''
        client_spec += "Client: %s\n\n" % self.p4client
        client_spec += "Owner: %s\n\n" % self.p4user
        client_spec += "Description:\n\tCreated by %s\n\n" % self.p4user
        client_spec += "Root:\t%s\n\n" % self.builder.basedir
        client_spec += "Options:\tallwrite rmdir\n\n"
        client_spec += "LineEnd:\tlocal\n\n"

        # Setup a view
        client_spec += "View:\n\t%s" % (self.p4base)
        if self.p4branch:
            client_spec += "%s/" % (self.p4branch)
        client_spec += "... //%s/%s/...\n" % (self.p4client, self.srcdir)
        if self.p4extra_views:
            for k, v in self.p4extra_views:
                client_spec += "\t%s/... //%s/%s%s/...\n" % (k, self.p4client,
                                                             self.srcdir, v)
        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            command.extend(['-P', self.p4passwd])
        command.extend(['client', '-i'])
        log.msg(client_spec)
        c = ShellCommand(self.builder, command, self.builder.basedir,
                         environ=env, sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, initialStdin=client_spec,
                         usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        d.addCallback(lambda _: self._doP4Sync(force=True))
        return d

    def parseGotRevision(self):
        rv = None
        if self.revision:
            rv = str(self.revision)
        return rv

registerSlaveCommand("p4", P4, command_version)


class P4Sync(P4Base):
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
        P4Base.setup(self, args)
        self.vcexe = getCommand("p4")

    def sourcedirIsUpdateable(self):
        return True

    def _doVC(self, force):
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
        if force:
            command.extend(['-f'])
        if self.revision:
            command.extend(['@' + self.revision])
        env = {}
        c = ShellCommand(self.builder, command, d, environ=env,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCUpdate(self):
        return self._doVC(force=False)

    def doVCFull(self):
        return self._doVC(force=True)

    def parseGotRevision(self):
        rv = None
        if self.revision:
            rv = str(self.revision)
        return rv

registerSlaveCommand("p4sync", P4Sync, command_version)
