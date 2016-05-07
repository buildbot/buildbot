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
import re
import textwrap

from twisted.internet import defer
from twisted.python import log

from buildslave import runprocess
from buildslave.commands.base import AbandonChain
from buildslave.commands.base import SourceBaseCommand


class Repo(SourceBaseCommand):

    """Repo specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['manifest_url'] (required):    The manifests repo repository.
    ['manifest_branch'] (optional): Which manifest repo version (i.e. branch or tag)
                                    to retrieve. Default: "master".
    ['manifest_file'] (optional):   Which manifest file to use. Default: "default.xml".
    ['manifest_override_url'] (optional):   Which manifest file to use as an overide. Default: None.
                                    This is usually set by forced build to build over a known working base
    ['tarball'] (optional):         The tarball base to accelerate the fetch.
    ['repo_downloads'] (optional):  Repo downloads to do. Computer from GerritChangeSource
                                    and forced build properties.
    ['jobs'] (optional):            number of connections to run in parallel
                                    repo tool will use while syncing
    """

    header = "repo operation"
    requiredArgs = ['manifest_url']

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.manifest_url = args.get('manifest_url')
        self.manifest_branch = args.get('manifest_branch')
        self.manifest_file = args.get('manifest_file')
        self.manifest_override_url = args.get('manifest_override_url')
        self.tarball = args.get('tarball')
        self.repo_downloads = args.get('repo_downloads')
        # we're using string instead of an array here, because it will be transferred back
        # to the master as string anyway and using eval() could have security
        # implications.
        self.repo_downloaded = ""
        self.jobs = args.get('jobs')

        self.sourcedata = "%s %s" % (self.manifest_url, self.manifest_file)
        self.re_change = re.compile(
            r".* refs/changes/\d\d/(\d+)/(\d+) -> FETCH_HEAD$")
        self.re_head = re.compile("^HEAD is now at ([0-9a-f]+)...")

    def _fullSrcdir(self):
        return os.path.join(self.builder.basedir, self.srcdir)

    def sourcedirIsUpdateable(self):
        log.msg(os.path.join(self._fullSrcdir(), ".repo"))
        log.msg(os.path.isdir(os.path.join(self._fullSrcdir(), ".repo")))
        return os.path.isdir(os.path.join(self._fullSrcdir(), ".repo"))

    def _repoCmd(self, command, cb=None, abandonOnFailure=True, **kwargs):
        repo = self.getCommand("repo")
        c = runprocess.RunProcess(self.builder, [repo] + command, self._fullSrcdir(),
                                  sendRC=False, timeout=self.timeout,
                                  maxTime=self.maxTime, usePTY=False,
                                  logEnviron=self.logEnviron, **kwargs)
        self.command = c
        d = c.start()
        if cb:
            if abandonOnFailure:
                d.addCallback(self._abandonOnFailure)
            d.addCallback(cb)
        return d

    def _Cmd(self, cmds, callback, abandonOnFailure=True):
        c = runprocess.RunProcess(self.builder, cmds, self._fullSrcdir(),
                                  sendRC=False, timeout=self.timeout,
                                  maxTime=self.maxTime, usePTY=False,
                                  logEnviron=self.logEnviron)
        self.command = c
        d = c.start()
        if abandonOnFailure:
            d.addCallback(self._abandonOnFailure)
        d.addCallback(callback)
        return d

    def sourcedataMatches(self):
        try:
            olddata = self.readSourcedata()
            return olddata == self.sourcedata
        except IOError:
            return False

    def doVCFull(self):
        os.makedirs(self._fullSrcdir())
        if self.tarball and os.path.exists(self.tarball):
            return self._Cmd(['tar', '-xvzf', self.tarball], self._doPreInitCleanUp)
        else:
            return self._doInit(None)

    def _doInit(self, res):
        # on fresh init, this file may confuse repo.
        if os.path.exists(os.path.join(self._fullSrcdir(), ".repo/project.list")):
            os.unlink(os.path.join(self._fullSrcdir(), ".repo/project.list"))
        return self._repoCmd(['init', '-u', self.manifest_url, '-b', self.manifest_branch, '-m', self.manifest_file], self._didInit)

    def _didInit(self, res):
        return self.doVCUpdate()

    def doVCUpdate(self):
        if self.repo_downloads:
            self.sendStatus({'header': "will download:\n" + "repo download " +
                             "\nrepo download ".join(self.repo_downloads) + "\n"})
        return self._doPreSyncCleanUp(None)

    # a simple shell script to gather all cleanup tweaks...
    # doing them one by one just complicate the stuff
    # and messup the stdio log
    def _cleanupCommand(self):
        command = textwrap.dedent("""\
            set -v
            if [ -d .repo/manifests ]
            then
                # repo just refuse to run if manifest is messed up
                # so ensure we are in a known state
                    cd .repo/manifests
                git fetch origin
                git reset --hard remotes/origin/%(manifest_branch)s
                git config branch.default.merge %(manifest_branch)s
                cd ..
                ln -sf manifests/%(manifest_file)s manifest.xml
                cd ..
             fi
             repo forall -c rm -f .git/index.lock
               repo forall -c git clean -f -d -x 2>/dev/null
                repo forall -c git reset --hard HEAD 2>/dev/null
             """) % self.__dict__
        return "\n".join([s.strip() for s in command.splitlines()])

    def _doPreInitCleanUp(self, dummy):
        command = self._cleanupCommand()
        return self._Cmd(["bash", "-c", command], self._doInit, abandonOnFailure=False)

    def _doPreSyncCleanUp(self, dummy):
        command = self._cleanupCommand()
        return self._Cmd(["bash", "-c", command], self._doManifestOveride, abandonOnFailure=False)

    def _doManifestOveride(self, dummy):
        if self.manifest_override_url:
            self.sendStatus(
                {"header": "overriding manifest with %s\n" % (self.manifest_override_url)})
            if os.path.exists(os.path.join(self._fullSrcdir(), self.manifest_override_url)):
                os.system("cd %s; cp -f %s manifest_override.xml" %
                          (self._fullSrcdir(), self.manifest_override_url))
            else:
                command = [
                    "wget", self.manifest_override_url, '-O', 'manifest_override.xml']
                return self._Cmd(command, self._doSync)
        return self._doSync(None)

    def _doSync(self, dummy):
        if self.manifest_override_url:
            os.system(
                "cd %s/.repo; ln -sf ../manifest_override.xml manifest.xml" % (self._fullSrcdir()))
        command = ['sync']
        if self.jobs:
            command.append('-j' + str(self.jobs))
        self.sendStatus({"header": "synching manifest %s from branch %s from %s\n"
                                   % (self.manifest_file, self.manifest_branch, self.manifest_url)})
        return self._repoCmd(command, self._didSync)

    def _didSync(self, dummy):
        if self.tarball and not os.path.exists(self.tarball):
            return self._Cmd(['tar', '-cvzf', self.tarball, ".repo"], self._doManifest)
        else:
            return self._doManifest(None)

    def _doManifest(self, dummy):
        command = ['manifest', '-r', '-o', 'manifest-original.xml']
        return self._repoCmd(command, self._doDownload, abandonOnFailure=False)

    def _doDownload(self, dummy):
        if hasattr(self.command, 'stderr') and self.command.stderr:
            if "Automatic cherry-pick failed" in self.command.stderr or "Automatic revert failed" in self.command.stderr:
                command = ['forall', '-c', 'git', 'diff', 'HEAD']
                self.cherry_pick_failed = True
                # call again
                return self._repoCmd(command, self._DownloadAbandon, abandonOnFailure=False, keepStderr=True)

            lines = self.command.stderr.split('\n')
            if len(lines) > 2:
                match1 = self.re_change.match(lines[1])
                match2 = self.re_head.match(lines[-2])
                if match1 and match2:
                    self.repo_downloaded += "%s/%s %s " % (
                        match1.group(1), match1.group(2), match2.group(1))

        if self.repo_downloads:
            # download each changeset while the self.download variable is not
            # empty
            download = self.repo_downloads.pop(0)
            command = ['download'] + download.split(' ')
            self.sendStatus({"header": "downloading changeset %s\n"
                                       % (download)})
            # call again
            return self._repoCmd(command, self._doDownload, abandonOnFailure=False, keepStderr=True)

        if self.repo_downloaded:
            self.sendStatus({"repo_downloaded": self.repo_downloaded[:-1]})
        return defer.succeed(0)

    def maybeNotDoVCFallback(self, res):
        # If we were unable to find the branch/SHA on the remote,
        # clobbering the repo won't help any, so just abort the chain
        if hasattr(self.command, 'stderr'):
            if "Couldn't find remote ref" in self.command.stderr:
                raise AbandonChain(-1)
            if hasattr(self, 'cherry_pick_failed') or "Automatic cherry-pick failed" in self.command.stderr:
                raise AbandonChain(-1)

    def _DownloadAbandon(self, dummy):
        self.sendStatus({"header": "abandonned due to merge failure\n"})
        raise AbandonChain(-1)
