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

from twisted.internet import defer

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
from buildslave.commands.base import AbandonChain


class Repo(SourceBaseCommand):
    """Repo specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['manifest_url'] (required):    The manifests repo repository.
    ['manifest_branch'] (optional): Which manifest repo version (i.e. branch or tag)
                                    to retrieve. Default: "master".
    ['manifest_file'] (optional):   Which manifest file to use. Default: "default.xml".
    ['tarball'] (optional):         The tarball base to accelerate the fetch.
    ['repo_downloads'] (optional):  Repo downloads to do. Computer from GerritChangeSource
                                    and forced build properties.
    """

    header = "repo operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.manifest_url = args.get('manifest_url')
        self.manifest_branch = args.get('manifest_branch')
        self.manifest_file =  args.get('manifest_file')
        self.tarball = args.get('tarball')
        self.repo_downloads = args.get('repo_downloads')
        # we're using string instead of an array here, because it will be transferred back
        # to the master as string anyway and using eval() could have security implications.
        self.repo_downloaded = ""

        self.sourcedata = "%s %s %s" % (self.manifest_url, self.manifest_branch, self.manifest_file)
        self.re_change = re.compile(".* refs/changes/\d\d/(\d+)/(\d+) -> FETCH_HEAD$")
        self.re_head = re.compile("^HEAD is now at ([0-9a-f]+)...")

    def _fullSrcdir(self):
        return os.path.join(self.builder.basedir, self.srcdir)

    def sourcedirIsUpdateable(self):
        print os.path.join(self._fullSrcdir(), ".repo")
        print os.path.isdir(os.path.join(self._fullSrcdir(), ".repo"))
        return os.path.isdir(os.path.join(self._fullSrcdir(), ".repo"))

    def _repoCmd(self, command, cb=None, abandonOnFailure=True, **kwargs):
        repo = self.getCommand("repo")
        c = runprocess.RunProcess(self.builder, [repo] + command, self._fullSrcdir(),
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False, **kwargs)
        self.command = c
        d = c.start()
        if cb:
            if abandonOnFailure:
                d.addCallback(self._abandonOnFailure)
            d.addCallback(cb)
        return d

    def _tarCmd(self, cmds, callback):
        cmd = ["tar"] + cmds
        c = runprocess.RunProcess(self.builder, cmd, self._fullSrcdir(),
                                  sendRC=False, timeout=self.timeout,
                                  maxTime=self.maxTime, usePTY=False)
        self.command = c
        cmdexec = c.start()
        cmdexec.addCallback(callback)
        return cmdexec

    def _gitCmd(self, subdir, cmds, callback):
        cmd = ["git"] + cmds
        c = runprocess.RunProcess(self.builder, cmd, os.path.join(self._fullSrcdir(), subdir),
                                  sendRC=False, timeout=self.timeout,
                                  maxTime=self.maxTime, usePTY=False)
        self.command = c
        cmdexec = c.start()
        cmdexec.addCallback(callback)
        return cmdexec

    def sourcedataMatches(self):
        try:
            olddata = self.readSourcedata()
            return olddata == self.sourcedata
        except IOError:
            return False

    def doVCFull(self):
        os.makedirs(self._fullSrcdir())
        if self.tarball and os.path.exists(self.tarball):
            return self._tarCmd(['-xvzf', self.tarball], self._doInit)
        else:
            return self._doInit(None)

    def _doInit(self,res):
        # on fresh init, this file may confuse repo.
        if os.path.exists(os.path.join(self._fullSrcdir(), ".repo/project.list")):
            os.unlink(os.path.join(self._fullSrcdir(), ".repo/project.list"))
        return self._repoCmd(['init', '-u', self.manifest_url, '-b', self.manifest_branch, '-m', self.manifest_file], self._didInit)

    def _didInit(self, res):
        return self.doVCUpdate()

    def doVCUpdate(self):
        command = ['forall', '-c', 'git', 'clean', '-f', '-d', '-x']
        return self._repoCmd(command, self._doClean2, abandonOnFailure=False)

    def _doClean2(self,dummy):
        command = ['clean', '-f', '-d', '-x']
        return self._gitCmd(".repo/manifests",command, self._doSync)

    def _doSync(self, dummy):
        command = ['sync']
        self.sendStatus({"header": "synching manifest %s from branch %s from %s\n"
                                   % (self.manifest_file, self.manifest_branch, self.manifest_url)})
        return self._repoCmd(command, self._didSync)

    def _didSync(self, dummy):
        if self.tarball and not os.path.exists(self.tarball):
            return self._tarCmd(['-cvzf', self.tarball, ".repo"], self._doDownload)
        else:
            return self._doDownload(None)

    def _doDownload(self, dummy):
        if hasattr(self.command, 'stderr') and self.command.stderr:
            lines = self.command.stderr.split('\n')
            if len(lines) > 2:
                match1 = self.re_change.match(lines[1])
                match2 = self.re_head.match(lines[-2])
                if match1 and match2:
                    self.repo_downloaded += "%s/%s %s " % (match1.group(1), match1.group(2), match2.group(1))

        if self.repo_downloads:
            # download each changeset while the self.download variable is not empty
            download = self.repo_downloads.pop(0)
            command = ['download'] + download.split(' ')
            self.sendStatus({"header": "downloading changeset %s\n"
                                       % (download)})
            return self._repoCmd(command, self._doDownload, keepStderr=True) # call again

        if self.repo_downloaded:
            self.sendStatus({"repo_downloaded": self.repo_downloaded[:-1]})
        return defer.succeed(0)

    def maybeNotDoVCFallback(self, res):
        # If we were unable to find the branch/SHA on the remote,
        # clobbering the repo won't help any, so just abort the chain
        if hasattr(self.command, 'stderr'):
            if "Couldn't find remote ref" in self.command.stderr:
                raise AbandonChain(-1)

