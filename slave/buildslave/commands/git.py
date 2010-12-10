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

from twisted.internet import defer

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
from buildslave.commands.base import AbandonChain


class Git(SourceBaseCommand):
    """Git specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['repourl'] (required):         the upstream GIT repository string
    ['branch'] (optional):          which version (i.e. branch or tag)
                                    to retrieve. Default: "master".
    ['submodules'] (optional):      whether to initialize and update
                                    submodules. Default: False.
    ['ignore_ignores']: (optional): ignore ignores when purging changes.
    ['reference'] (optional):       use this reference repository
                                    to fetch objects.
    ['gerrit_branch']: (optional):  which virtual branch to retrieve.
    """

    header = "git operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.repourl = args['repourl']
        self.branch = args.get('branch')
        if not self.branch:
            self.branch = "master"
        self.sourcedata = "%s %s\n" % (self.repourl, self.branch)
        self.submodules = args.get('submodules')
        self.ignore_ignores = args.get('ignore_ignores', True)
        self.reference = args.get('reference', None)
        self.gerrit_branch = args.get('gerrit_branch', None)

    def _fullSrcdir(self):
        return os.path.join(self.builder.basedir, self.srcdir)

    def _commitSpec(self):
        if self.revision:
            return self.revision
        return self.branch

    def sourcedirIsUpdateable(self):
        return os.path.isdir(os.path.join(self._fullSrcdir(), ".git"))

    def _dovccmd(self, command, cb=None, **kwargs):
        git = self.getCommand("git")
        c = runprocess.RunProcess(self.builder, [git] + command, self._fullSrcdir(),
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
        d = self._dovccmd(command, self._didHeadCheckout)
        if self.gerrit_branch:
            d.addErrback(self._doFetchGerritChange)
        return d

    def maybeNotDoVCFallback(self, res):
        # If we were unable to find the branch/SHA on the remote,
        # clobbering the repo won't help any, so just abort the chain
        if hasattr(self.command, 'stderr'):
            if "Couldn't find remote ref" in self.command.stderr:
                raise AbandonChain(-1)

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
        # If the 'progress' option is set, tell git fetch to output
        # progress information to the log. This can solve issues with
        # long fetches killed due to lack of output, but only works
        # with Git 1.7.2 or later.
        if self.args.get('progress'):
            command.append('--progress')
        self.sendStatus({"header": "fetching branch %s from %s\n"
                                        % (self.branch, self.repourl)})
        return self._dovccmd(command, self._didFetch, keepStderr=True)

    def _doFetchGerritChange(self, dummy):
        # The plus will make sure the repo is moved to the branch's
        # head even if it is not a simple "fast-forward"
        command = ['fetch', '-t', self.repourl, '+%s' % self.gerrit_branch]
        # If the 'progress' option is set, tell git fetch to output
        # progress information to the log. This can solve issues with
        # long fetches killed due to lack of output, but only works
        # with Git 1.7.2 or later.
        if self.args.get('progress'):
            command.append('--progress')
        self.sendStatus({"header": "fetching branch %s from %s\n"
                                        % (self.gerrit_branch, self.repourl)})
        # Clear gerrit_branch, so that we could re-use _didFetch().
        self.gerrit_branch = None
        return self._dovccmd(command, self._didFetch, keepStderr=True)

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
        # If we have a reference repository specified, we need to also set that
        # up after the 'git init'.
        if self.reference:
            git_alts_path = os.path.join(self._fullSrcdir(), '.git', 'objects', 'info', 'alternates')
            git_alts_file = open(git_alts_path, 'w')
            git_alts_file.write(os.path.join(self.reference, 'objects'))
            git_alts_file.close()
        return self.doVCUpdate()

    def doVCFull(self):
        git = self.getCommand("git")

        # If they didn't ask for a specific revision, we can get away with a
        # shallow clone.
        if not self.args.get('revision') and self.args.get('shallow'):
            cmd = [git, 'clone', '--depth', '1']
            # If we have a reference repository, pass it to the clone command
            if self.reference:
                cmd.extend(['--reference', self.reference])
            cmd.extend([self.repourl, self._fullSrcdir()])
            c = runprocess.RunProcess(self.builder, cmd, self.builder.basedir,
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

