import os
from xml.dom.minidom import parseString

from twisted.python import log

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
from buildslave.commands import utils
from buildslave.util import Obfuscated

class SVN(SourceBaseCommand):
    """Subversion-specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

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
        SourceBaseCommand.setup(self, args)
        self.vcexe = utils.getCommand("svn")
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
        c = runprocess.RunProcess(self.builder, fullCmd, rootdir,
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
        return self._dovccmd('update', ['--revision', str(revision)])

    def doVCFull(self):
        revision = self.args['revision'] or 'HEAD'
        args = ['--revision', str(revision), self.svnurl, self.srcdir]
        if self.mode == "export":
            command = 'export'
        else:
            # mode=='clobber', or copy/update on a broken workspace
            command = 'checkout'
        return self._dovccmd(command, args, rootdir=self.builder.basedir)

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
                utils.rmdirRecursive(filepath)
        # Now safe to update.
        revision = self.args['revision'] or 'HEAD'
        return self._dovccmd('update', ['--revision', str(revision)],
                             keepStdout=True)

    def getSvnVersionCommand(self):
        """
        Get the (shell) command used to determine SVN revision number
        of checked-out code

        return: list of strings, passable as the command argument to RunProcess
        """
        # svn checkout operations finish with 'Checked out revision 16657.'
        # svn update operations finish the line 'At revision 16654.'
        # But we don't use those. Instead, run 'svnversion'.
        svnversion_command = utils.getCommand("svnversion")
        # older versions of 'svnversion' (1.1.4) require the WC_PATH
        # argument, newer ones (1.3.1) do not.
        return [svnversion_command, "."]

    def parseGotRevision(self):
        c = runprocess.RunProcess(self.builder,
                         self.getSvnVersionCommand(),
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env, timeout=self.timeout,
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
