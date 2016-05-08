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


import os
import shutil
import sys
from base64 import b64encode

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import threads
from twisted.python import failure
from twisted.python import log
from twisted.python import runtime
from zope.interface import implements

from buildbot_worker import runprocess
from buildbot_worker import util
from buildbot_worker.commands import utils
from buildbot_worker.exceptions import AbandonChain
from buildbot_worker.interfaces import IWorkerCommand

# this used to be a CVS $-style "Revision" auto-updated keyword, but since I
# moved to Darcs as the primary repository, this is updated manually each
# time this file is changed. The last cvs_ver that was here was 1.51 .
command_version = "2.16"

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
#  >= 2.11: Arch, Bazaar, and Monotone removed
#  >= 2.12: SlaveShellCommand no longer accepts 'keep_stdin_open'
#  >= 2.13: SlaveFileUploadCommand supports option 'keepstamp'
#  >= 2.14: RemoveDirectory can delete multiple directories
#  >= 2.15: 'interruptSignal' option is added to SlaveShellCommand
#  >= 2.16: 'sigtermTime' option is added to SlaveShellCommand
# >= 2.16: runprocess supports obfuscation via tuples (#1748)
#  >= 2.16: listdir command added to read a directory


class Command(object):
    implements(IWorkerCommand)

    """This class defines one command that can be invoked by the build master.
    The command is executed on the worker side, and always sends back a
    completion message when it finishes. It may also send intermediate status
    as it runs (by calling builder.sendStatus). Some commands can be
    interrupted (either by the build master or a local timeout), in which
    case the step is expected to complete normally with a status message that
    indicates an error occurred.

    These commands are used by BuildSteps on the master side. Each kind of
    BuildStep uses a single Command. The worker must implement all the
    Commands required by the set of BuildSteps used for any given build:
    this is checked at startup time.

    All Commands are constructed with the same signature:
     c = CommandClass(builder, stepid, args)
    where 'builder' is the parent WorkerForBuilder object, and 'args' is a
    dict that is interpreted per-command.

    The setup(args) method is available for setup, and is run from __init__.
    Mandatory args can be declared by listing them in the requiredArgs property.
    They will be checked before calling the setup(args) method.

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

    requiredArgs = []
    debug = False
    interrupted = False
    # set by Builder, cleared on shutdown or when the Deferred fires
    running = False

    _reactor = reactor

    def __init__(self, builder, stepId, args):
        self.builder = builder
        self.stepId = stepId  # just for logging
        self.args = args
        self.startTime = None

        missingArgs = [arg for arg in self.requiredArgs if arg not in args]
        if missingArgs:
            raise ValueError("%s is missing args: %s" %
                             (self.__class__.__name__, ", ".join(missingArgs)))
        self.setup(args)

    def setup(self, args):
        """Override this in a subclass to extract items from the args dict."""
        pass

    def doStart(self):
        self.running = True
        self.startTime = util.now(self._reactor)
        d = defer.maybeDeferred(self.start)

        def commandComplete(res):
            self.sendStatus(
                {"elapsed": util.now(self._reactor) - self.startTime})
            self.running = False
            return res
        d.addBoth(commandComplete)
        return d

    def start(self):
        """Start the command. This method should return a Deferred that will
        fire when the command has completed. The Deferred's argument will be
        ignored.

        This method should be overridden by subclasses."""
        raise NotImplementedError("You must implement this in a subclass")

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

    # utility methods, mostly used by WorkerShellCommand and the like

    def _abandonOnFailure(self, rc):
        if not isinstance(rc, int):
            log.msg("weird, _abandonOnFailure was given rc=%s (%s)" %
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


class SourceBaseCommand(Command):

    """Abstract base class for Version Control System operations (checkout
    and update). This class extracts the following arguments from the
    dictionary received from the master:

        - ['workdir']:  (required) the subdirectory where the buildable sources
                        should be placed

        - ['mode']:     one of update/copy/clobber/export, defaults to 'update'

        - ['revision']: (required) If not None, this is an int or string which indicates
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
                        DELAY seconds. This is intended to deal with workers
                        that experience transient network failures.
    """

    sourcedata = ""

    def setup(self, args):
        # if we need to parse the output, use this environment. Otherwise
        # command output will be in whatever the worker's native language
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
        self.logEnviron = args.get('logEnviron', True)
        self._commandPaths = {}
        # VC-specific subclasses should override this to extract more args.
        # Make sure to upcall!

    def getCommand(self, name):
        """Wrapper around utils.getCommand that will output a resonable
        error message and raise AbandonChain if the command cannot be
        found"""
        if name not in self._commandPaths:
            try:
                self._commandPaths[name] = utils.getCommand(name)
            except RuntimeError:
                self.sendStatus({'stderr': "could not find '%s'\n" % name})
                self.sendStatus(
                    {'stderr': "PATH is '%s'\n" % os.environ.get('PATH', '')})
                raise AbandonChain(-1)
        return self._commandPaths[name]

    def start(self):
        self.sendStatus({'header': "starting " + self.header + "\n"})
        self.command = None

        # self.srcdir is where the VC system should put the sources
        if self.mode == "copy":
            self.srcdir = "source"  # hardwired directory name, sorry
        else:
            self.srcdir = self.workdir

        self.sourcedatafile = os.path.join(self.builder.basedir,
                                           ".buildbot-sourcedata-" + b64encode(self.srcdir))

        # upgrade older versions to the new sourcedata location
        old_sd_path = os.path.join(
            self.builder.basedir, self.srcdir, ".buildbot-sourcedata")
        if os.path.exists(old_sd_path) and not os.path.exists(self.sourcedatafile):
            os.rename(old_sd_path, self.sourcedatafile)

        # also upgrade versions that didn't include the encoded version of the
        # source directory
        old_sd_path = os.path.join(
            self.builder.basedir, ".buildbot-sourcedata")
        if os.path.exists(old_sd_path) and not os.path.exists(self.sourcedatafile):
            os.rename(old_sd_path, self.sourcedatafile)

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
            d.addBoth(self.maybeDoVCFallback)
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
        """
        Read the sourcedata file and return its contents

        @returns: source data
        @raises: IOError if the file does not exist
        """
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
        if isinstance(rc, int) and rc == 0:
            return rc
        if self.interrupted:
            raise AbandonChain(1)

        # allow AssertionErrors to fall through, for benefit of the tests; for
        # all other errors, carry on to try the fallback
        if isinstance(rc, failure.Failure) and rc.check(AssertionError):
            return rc

        # Let VCS subclasses have an opportunity to handle
        # unrecoverable errors without having to clobber the repo
        self.maybeNotDoVCFallback(rc)
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

    def maybeNotDoVCFallback(self, rc):
        """Override this in a subclass if you want to detect unrecoverable
        checkout errors where clobbering the repo wouldn't help, and stop
        the current VC chain before it clobbers the repo for future builds.

        Use 'raise AbandonChain' to pass up a halt if you do detect such."""
        pass

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
                return res  # don't re-try interrupted builds
            res.trap(AbandonChain)
        else:
            if isinstance(res, int) and res == 0:
                return res
            if self.interrupted:
                raise AbandonChain(1)
        # if we get here, we should retry, if possible
        if self.retry:
            delay, repeats = self.retry
            if repeats >= 0:
                self.retry = (delay, repeats - 1)
                msg = ("update failed, trying %d more times after %d seconds"
                       % (repeats, delay))
                self.sendStatus({'header': msg + "\n"})
                log.msg(msg)
                d = defer.Deferred()
                # we are going to do a full checkout, so a clobber is
                # required first
                self.doClobber(d, self.workdir)
                if self.srcdir:
                    self.doClobber(d, self.srcdir)
                d.addCallback(lambda res: self.doVCFull())
                d.addBoth(self.maybeDoVCRetry)
                self._reactor.callLater(delay, d.callback, None)
                return d
        return res

    def doClobber(self, dummy, dirname, chmodDone=False):
        d = os.path.join(self.builder.basedir, dirname)
        if runtime.platformType != "posix":
            d = threads.deferToThread(utils.rmdirRecursive, d)

            def cb(_):
                return 0  # rc=0

            def eb(f):
                self.sendStatus(
                    {'header': 'exception from rmdirRecursive\n' + f.getTraceback()})
                return -1  # rc=-1
            d.addCallbacks(cb, eb)
            return d
        command = ["rm", "-rf", d]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                                  sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                                  logEnviron=self.logEnviron, usePTY=False)

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

        command = ["chmod", "-Rf", "u+rwx",
                   os.path.join(self.builder.basedir, dirname)]
        if sys.platform.startswith('freebsd'):
            # Work around a broken 'chmod -R' on FreeBSD (it tries to recurse into a
            # directory for which it doesn't have permission, before changing that
            # permission) by running 'find' instead
            command = ["find", os.path.join(self.builder.basedir, dirname),
                       '-exec', 'chmod', 'u+rwx', '{}', ';']
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                                  sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                                  logEnviron=self.logEnviron, usePTY=False)

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
            d = threads.deferToThread(shutil.copytree, fromdir, todir)

            def cb(_):
                return 0  # rc=0

            def eb(f):
                self.sendStatus(
                    {'header': 'exception from copytree\n' + f.getTraceback()})
                return -1  # rc=-1
            d.addCallbacks(cb, eb)
            return d

        if not os.path.exists(os.path.dirname(todir)):
            os.makedirs(os.path.dirname(todir))
        if os.path.exists(todir):
            # I don't think this happens, but just in case..
            log.msg(
                "cp target '%s' already exists -- cp will not do what you think!" % todir)

        command = ['cp', '-R', '-P', '-p', fromdir, todir]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                                  sendRC=False, timeout=self.timeout, maxTime=self.maxTime,
                                  logEnviron=self.logEnviron, usePTY=False)
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
            utils.getCommand("patch"),
            '-p%d' % patchlevel,
            '--remove-empty-files',
            '--force',
            '--forward',
            '-i', '.buildbot-diff',
        ]
        dir = os.path.join(self.builder.basedir, self.workdir)
        # Mark the directory so we don't try to update it later, or at least try
        # to revert first.
        open(os.path.join(dir, ".buildbot-patched"), "w").write("patched\n")

        # write the diff to a file, for reading later
        open(os.path.join(dir, ".buildbot-diff"), "w").write(diff)

        # Update 'dir' with the 'root' option. Make sure it is a subdirectory
        # of dir.
        if (root and
            os.path.abspath(os.path.join(dir, root)
                            ).startswith(os.path.abspath(dir))):
            dir = os.path.join(dir, root)

        # now apply the patch
        c = runprocess.RunProcess(self.builder, command, dir,
                                  sendRC=False, timeout=self.timeout,
                                  maxTime=self.maxTime, logEnviron=self.logEnviron,
                                  usePTY=False)
        self.command = c
        d = c.start()

        # clean up the temp file
        def cleanup(x):
            try:
                os.unlink(os.path.join(dir, ".buildbot-diff"))
            except OSError:
                pass
            return x
        d.addBoth(cleanup)

        d.addCallback(self._abandonOnFailure)
        return d

    def setFileContents(self, filename, contents):
        """Put the given C{contents} in C{filename}; this is a bit more
        succinct than opening, writing, and closing, and has the advantage of
        being patchable in tests.  Note that the enclosing directory is
        not automatically created, nor is this an "atomic" overwrite."""
        f = open(filename, 'w')
        f.write(contents)
        f.close()
