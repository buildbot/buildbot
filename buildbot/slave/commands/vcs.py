import os, re, sys, shutil, time

from xml.dom.minidom import parseString

from twisted.python import log, failure, runtime
from twisted.internet import defer, reactor

from buildbot.slave.commands.base import Command, ShellCommand, AbandonChain, command_version, Obfuscated
from buildbot.slave.commands.registry import registerSlaveCommand
from buildbot.slave.commands.utils import getCommand, rmdirRecursive
from buildbot.util import remove_userpassword

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
                # we are going to do a full checkout, so a clobber is
                # required first
                self.doClobber(d, self.workdir)
                d.addCallback(lambda res: self.doVCFull())
                d.addBoth(self.maybeDoVCRetry)
                self._reactor.callLater(delay, d.callback, None)
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

        command = ["chmod", "-Rf", "u+rwx", os.path.join(self.builder.basedir, dirname)]
        if sys.platform.startswith('freebsd'):
            # Work around a broken 'chmod -R' on FreeBSD (it tries to recurse into a
            # directory for which it doesn't have permission, before changing that
            # permission) by running 'find' instead
            command = ["find", os.path.join(self.builder.basedir, dirname),
                                '-exec', 'chmod', 'u+rwx', '{}', ';' ]
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



class BK(SourceBase):
    """BitKeeper-specific VC operation. In addition to the arguments
    handled by SourceBase, this command reads the following keys:

    ['bkurl'] (required): the BK repository string
    """

    header = "bk operation"

    def setup(self, args):
        SourceBase.setup(self, args)
        self.vcexe = getCommand("bk")
        self.bkurl = args['bkurl']
        self.sourcedata = '"%s\n"' % self.bkurl

        self.bk_args = []
        if args.get('extra_args', None) is not None:
            self.bk_args.extend(args['extra_args'])

    def sourcedirIsUpdateable(self):
        if os.path.exists(os.path.join(self.builder.basedir,
                                       self.srcdir, ".buildbot-patched")):
            return False
        return os.path.isfile(os.path.join(self.builder.basedir,
                                          self.srcdir, "BK/parent"))

    def doVCUpdate(self):
        revision = self.args['revision'] or 'HEAD'
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)

        # Revision is ignored since the BK free client doesn't support it.
        command = [self.vcexe, 'pull']
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         keepStdout=True, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):

        revision_arg = ''
        if self.args['revision']:
            revision_arg = "-r%s" % self.args['revision']

        d = self.builder.basedir

        command = [self.vcexe, 'clone', revision_arg] + self.bk_args + \
                   [self.bkurl, self.srcdir]
        c = ShellCommand(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         keepStdout=True, usePTY=False)
        self.command = c
        return c.start()

    def getBKVersionCommand(self):
        """
        Get the (shell) command used to determine BK revision number
        of checked-out code

        return: list of strings, passable as the command argument to ShellCommand
        """
        return [self.vcexe, "changes", "-r+", "-d:REV:"]

    def parseGotRevision(self):
        c = ShellCommand(self.builder,
                         self.getBKVersionCommand(),
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            r_raw = c.stdout.strip()
            got_version = None
            try:
                r = r_raw
            except:
                msg = ("BK.parseGotRevision unable to parse output: (%s)" % r_raw)
                log.msg(msg)
                self.sendStatus({'header': msg + "\n"})
                raise ValueError(msg)
            return r
        d.addCallback(_parse)
        return d

registerSlaveCommand("bk", BK, command_version)




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
    ['checkout_options']: a list of strings to use after export,
                          but before revision and branch specifiers
    ['extra_options']: a list of strings to use after export and checkout,
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
        self.export_options = args.get('export_options', [])
        self.extra_options = args.get('extra_options', [])
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
        else:
            command += self.export_options
        command += self.extra_options

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
    ['depth']:             Pass depth argument to subversion 1.5+
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
            command = ['clean', '-f', '-d']
            if self.ignore_ignores:
                command.append('-x')
            return self._dovccmd(command, self._didClean)
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
        # If they didn't ask for a specific revision, we can get away with a
        # shallow clone.
        if not self.args.get('revision') and self.args.get('shallow'):
            cmd = [self.vcexe, 'clone', '--depth', '1', self.repourl,
                   self._fullSrcdir()]
            c = ShellCommand(self.builder, cmd, self.builder.basedir,
                             sendRC=False, timeout=self.timeout,
                             maxTime=self.maxTime, usePTY=False)
            self.command = c
            cmdexec = c.start()
            cmdexec.addCallback(self._didInit)
            return cmdexec
        else:
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
        self.clobbercount = 0 # n times we've clobbered

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
        self.clobbercount += 1

        if self.clobbercount > 3:
            raise Exception, "Too many clobber attempts. Aborting step"

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
                else:
                    repourl = self.repourl

                if repourl.startswith('file://'):
                    repourl = repourl.split('file://')[1]
                if oldurl.startswith('file://'):
                    oldurl = oldurl.split('file://')[1]

                oldurl = remove_userpassword(oldurl)
                repourl = remove_userpassword(repourl)

                if oldurl.rstrip('/') != repourl.rstrip('/'):
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
        command = [self.vcexe, "identify", "--id", "--debug"] # get full rev id
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
            command.extend(['-P', Obfuscated(self.p4passwd, "XXXXXXXX")])
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
            command.extend(['-P', Obfuscated(self.p4passwd, "XXXXXXXX")])
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
            command.extend(['-P', Obfuscated(self.p4passwd, "XXXXXXXX")])
        command.extend(['client', '-i'])
        log.msg(client_spec)

        # from bdbaddog in github comments:
        # I'm pretty sure the issue is that perforce client specs can't be
        # non-ascii (unless you configure at initial config to be unicode). I
        # floated a question to perforce mailing list.  From reading the
        # internationalization notes..
        #   http://www.perforce.com/perforce/doc.092/user/i18nnotes.txt
        # I'm 90% sure that's the case.
        # (http://github.com/bdbaddog/buildbot/commit/8420149b2b804efcf5f81a13e18aa62da0424d21)

        # Clean client spec to plain ascii
        client_spec=client_spec.encode('ascii','ignore')

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
        if self.revision:
            return str(self.revision)
        else:
            return P4Base.parseGotRevision(self)

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
            command.extend(['-P', Obfuscated(self.p4passwd, "XXXXXXXX")])
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
        if self.revision:
            return str(self.revision)
        else:
            return P4Base.parseGotRevision(self)

registerSlaveCommand("p4sync", P4Sync, command_version)
