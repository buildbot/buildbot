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

from __future__ import absolute_import
from __future__ import print_function

import re
import textwrap

from twisted.internet import defer
from twisted.internet import reactor
from zope.interface import implementer

from buildbot import util
from buildbot.interfaces import IRenderable
from buildbot.process import buildstep
from buildbot.steps.source.base import Source


@implementer(IRenderable)
class RepoDownloadsFromProperties(util.ComparableMixin, object):
    parse_download_re = (re.compile(r"repo download ([^ ]+) ([0-9]+/[0-9]+)"),
                         re.compile(r"([^ ]+) ([0-9]+/[0-9]+)"),
                         re.compile(r"([^ ]+)/([0-9]+/[0-9]+)"),
                         )

    compare_attrs = ('names',)

    def __init__(self, names):
        self.names = names

    def getRenderingFor(self, props):
        downloads = []
        for propName in self.names:
            s = props.getProperty(propName)
            if s is not None:
                downloads.extend(self.parseDownloadProperty(s))
        return downloads

    def parseDownloadProperty(self, s):
        """
         lets try to be nice in the format we want
         can support several instances of "repo download proj number/patch" (direct copy paste from gerrit web site)
         or several instances of "proj number/patch" (simpler version)
         This feature allows integrator to build with several pending interdependent changes.
         returns list of repo downloads sent to the worker
         """
        if s is None:
            return []
        ret = []
        for cur_re in self.parse_download_re:
            res = cur_re.search(s)
            while res:
                ret.append("%s %s" % (res.group(1), res.group(2)))
                s = s[:res.start(0)] + s[res.end(0):]
                res = cur_re.search(s)
        return ret


@implementer(IRenderable)
class RepoDownloadsFromChangeSource(util.ComparableMixin, object):
    compare_attrs = ('codebase',)

    def __init__(self, codebase=None):
        self.codebase = codebase

    def getRenderingFor(self, props):
        downloads = []
        if self.codebase is None:
            changes = props.getBuild().allChanges()
        else:
            changes = props.getBuild().getSourceStamp(self.codebase).changes
        for change in changes:
            if ("event.type" in change.properties and
                    change.properties["event.type"] == "patchset-created"):
                downloads.append("%s %s/%s" % (change.properties["event.change.project"],
                                               change.properties[
                                                   "event.change.number"],
                                               change.properties["event.patchSet.number"]))
        return downloads


class Repo(Source):

    """ Class for Repo with all the smarts """
    name = 'repo'
    renderables = ["manifestURL", "manifestBranch", "manifestFile", "tarball", "jobs",
                   "syncAllBranches", "updateTarballAge", "manifestOverrideUrl",
                   "repoDownloads", "depth"]

    ref_not_found_re = re.compile(r"fatal: Couldn't find remote ref")
    cherry_pick_error_re = re.compile(r"|".join([r"Automatic cherry-pick failed",
                                                 r"error: "
                                                 r"fatal: "
                                                 r"possibly due to conflict resolution."]))
    re_change = re.compile(r".* refs/changes/\d\d/(\d+)/(\d+) -> FETCH_HEAD$")
    re_head = re.compile(r"^HEAD is now at ([0-9a-f]+)...")
    # number of retries, if we detect mirror desynchronization
    mirror_sync_retry = 10
    # wait 1min between retries (thus default total retry time is 10min)
    mirror_sync_sleep = 60

    def __init__(self,
                 manifestURL=None,
                 manifestBranch="master",
                 manifestFile="default.xml",
                 tarball=None,
                 jobs=None,
                 syncAllBranches=False,
                 updateTarballAge=7 * 24.0 * 3600.0,
                 manifestOverrideUrl=None,
                 repoDownloads=None,
                 depth=0,
                 **kwargs):
        """
        @type  manifestURL: string
        @param manifestURL: The URL which points at the repo manifests repository.

        @type  manifestBranch: string
        @param manifestBranch: The manifest branch to check out by default.

        @type  manifestFile: string
        @param manifestFile: The manifest to use for sync.

        @type syncAllBranches: bool.
        @param syncAllBranches: true, then we must slowly synchronize all branches.

        @type updateTarballAge: float
        @param updateTarballAge: renderable to determine the update tarball policy,
                                 given properties
                               Returns: max age of tarball in seconds, or None, if we
                               want to skip tarball update

        @type manifestOverrideUrl: string
        @param manifestOverrideUrl: optional http URL for overriding the manifest
                                    usually coming from Property setup by a ForceScheduler

        @type repoDownloads: list of strings
        @param repoDownloads: optional repo download to perform after the repo sync

        @type depth: integer
        @param depth: optional depth parameter to repo init.
                          If specified, create a shallow clone with given depth.
        """
        self.manifestURL = manifestURL
        self.manifestBranch = manifestBranch
        self.manifestFile = manifestFile
        self.tarball = tarball
        self.jobs = jobs
        self.syncAllBranches = syncAllBranches
        self.updateTarballAge = updateTarballAge
        self.manifestOverrideUrl = manifestOverrideUrl
        if repoDownloads is None:
            repoDownloads = []
        self.repoDownloads = repoDownloads
        self.depth = depth
        Source.__init__(self, **kwargs)

        assert self.manifestURL is not None

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    def filterManifestPatches(self):
        """
        Patches to manifest projects are a bit special.
        repo does not support a way to download them automatically,
        so we need to implement the boilerplate manually.
        This code separates the manifest patches from the other patches,
        and generates commands to import those manifest patches.
        """
        manifest_unrelated_downloads = []
        manifest_related_downloads = []
        for download in self.repoDownloads:
            project, ch_ps = download.split(" ")[-2:]
            if (self.manifestURL.endswith("/" + project) or
                    self.manifestURL.endswith("/" + project + ".git")):
                ch, ps = map(int, ch_ps.split("/"))
                branch = "refs/changes/%02d/%d/%d" % (ch % 100, ch, ps)
                manifest_related_downloads.append(
                    ["git", "fetch", self.manifestURL, branch])
                manifest_related_downloads.append(
                    ["git", "cherry-pick", "FETCH_HEAD"])
            else:
                manifest_unrelated_downloads.append(download)
        self.repoDownloads = manifest_unrelated_downloads
        self.manifestDownloads = manifest_related_downloads

    def _repoCmd(self, command, abandonOnFailure=True, **kwargs):
        return self._Cmd(["repo"] + command, abandonOnFailure=abandonOnFailure, **kwargs)

    def _Cmd(self, command, abandonOnFailure=True, workdir=None, **kwargs):
        if workdir is None:
            workdir = self.workdir
        cmd = buildstep.RemoteShellCommand(workdir, command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout, **kwargs)
        self.lastCommand = cmd
        # does not make sense to logEnviron for each command (just for first)
        self.logEnviron = False
        cmd.useLog(self.stdio_log, False)
        self.stdio_log.addHeader(
            "Starting command: %s\n" % (" ".join(command), ))
        self.step_status.setText(["%s" % (" ".join(command[:2]))])
        d = self.runCommand(cmd)

        @d.addCallback
        def evaluateCommand(_):
            if abandonOnFailure and cmd.didFail():
                self.descriptionDone = "repo failed at: %s" % (
                    " ".join(command[:2]))
                self.stdio_log.addStderr(
                    "Source step failed while running command %s\n" % cmd)
                raise buildstep.BuildStepFailed()
            return cmd.rc
        return d

    def repoDir(self):
        return self.build.path_module.join(self.workdir, ".repo")

    def sourcedirIsUpdateable(self):
        return self.pathExists(self.repoDir())

    def startVC(self, branch, revision, patch):
        d = self.doStartVC()
        d.addErrback(self.failed)

    @defer.inlineCallbacks
    def doStartVC(self):
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        self.filterManifestPatches()

        if self.repoDownloads:
            self.stdio_log.addHeader(
                "will download:\n" + "repo download " + "\nrepo download ".join(self.repoDownloads) + "\n")

        self.willRetryInCaseOfFailure = True

        d = self.doRepoSync()

        @d.addErrback
        def maybeRetry(why):
            # in case the tree was corrupted somehow because of previous build
            # we clobber one time, and retry everything
            if why.check(buildstep.BuildStepFailed) and self.willRetryInCaseOfFailure:
                self.stdio_log.addStderr("got issue at first try:\n" + str(why) +
                                         "\nRetry after clobber...")
                return self.doRepoSync(forceClobber=True)
            return why  # propagate to self.failed
        yield d
        yield self.maybeUpdateTarball()

        # starting from here, clobbering will not help
        yield self.doRepoDownloads()
        self.setStatus(self.lastCommand, 0)
        yield self.finished(0)

    @defer.inlineCallbacks
    def doClobberStart(self):
        yield self.runRmdir(self.workdir)
        yield self.runMkdir(self.workdir)
        yield self.maybeExtractTarball()

    @defer.inlineCallbacks
    def doRepoSync(self, forceClobber=False):
        updatable = yield self.sourcedirIsUpdateable()
        if not updatable or forceClobber:
            # no need to re-clobber in case of failure
            self.willRetryInCaseOfFailure = False
            yield self.doClobberStart()
        yield self.doCleanup()
        yield self._repoCmd(['init',
                             '-u', self.manifestURL,
                             '-b', self.manifestBranch,
                             '-m', self.manifestFile,
                             '--depth', str(self.depth)])

        if self.manifestOverrideUrl:
            self.stdio_log.addHeader(
                "overriding manifest with %s\n" % (self.manifestOverrideUrl))
            local_file = yield self.pathExists(self.build.path_module.join(self.workdir,
                                                                           self.manifestOverrideUrl))
            if local_file:
                yield self._Cmd(["cp", "-f", self.manifestOverrideUrl, "manifest_override.xml"])
            else:
                yield self._Cmd(["wget", self.manifestOverrideUrl, "-O", "manifest_override.xml"])
            yield self._Cmd(["ln", "-sf", "../manifest_override.xml", "manifest.xml"],
                            workdir=self.build.path_module.join(self.workdir, ".repo"))

        for command in self.manifestDownloads:
            yield self._Cmd(command, workdir=self.build.path_module.join(self.workdir, ".repo", "manifests"))

        command = ['sync']
        if self.jobs:
            command.append('-j' + str(self.jobs))
        if not self.syncAllBranches:
            command.append('-c')
        self.step_status.setText(["repo sync"])
        self.stdio_log.addHeader("synching manifest %s from branch %s from %s\n"
                                 % (self.manifestFile, self.manifestBranch, self.manifestURL))
        yield self._repoCmd(command)

        command = ['manifest', '-r', '-o', 'manifest-original.xml']
        yield self._repoCmd(command)

    # check whether msg matches one of the
    # compiled regexps in self.re_error_messages
    def _findErrorMessages(self, error_re):
        for logname in ['stderr', 'stdout']:
            if not hasattr(self.lastCommand, logname):
                continue
            msg = getattr(self.lastCommand, logname)
            if not (re.search(error_re, msg) is None):
                return True
        return False

    def _sleep(self, delay):
        d = defer.Deferred()
        reactor.callLater(delay, d.callback, 1)
        return d

    @defer.inlineCallbacks
    def doRepoDownloads(self):
        self.repo_downloaded = ""
        for download in self.repoDownloads:
            command = ['download'] + download.split(' ')
            self.stdio_log.addHeader("downloading changeset %s\n"
                                     % (download))

            retry = self.mirror_sync_retry + 1
            while retry > 0:
                yield self._repoCmd(command, abandonOnFailure=False,
                                    collectStdout=True, collectStderr=True)
                if not self._findErrorMessages(self.ref_not_found_re):
                    break
                retry -= 1
                self.stdio_log.addStderr(
                    "failed downloading changeset %s\n" % (download))
                self.stdio_log.addHeader("wait one minute for mirror sync\n")
                yield self._sleep(self.mirror_sync_sleep)

            if retry == 0:
                self.descriptionDone = "repo: change %s does not exist" % download
                raise buildstep.BuildStepFailed()

            if self.lastCommand.didFail() or self._findErrorMessages(self.cherry_pick_error_re):
                # cherry pick error! We create a diff with status current workdir
                # in stdout, which reveals the merge errors and exit
                command = ['forall', '-c', 'git', 'diff', 'HEAD']
                yield self._repoCmd(command, abandonOnFailure=False)
                self.descriptionDone = "download failed: %s" % download
                raise buildstep.BuildStepFailed()

            if hasattr(self.lastCommand, 'stderr'):
                lines = self.lastCommand.stderr.split("\n")
                match1 = match2 = False
                for line in lines:
                    if not match1:
                        match1 = self.re_change.match(line)
                    if not match2:
                        match2 = self.re_head.match(line)
                if match1 and match2:
                    self.repo_downloaded += "%s/%s %s " % (match1.group(1),
                                                           match1.group(2),
                                                           match2.group(1))

        self.setProperty("repo_downloaded", self.repo_downloaded, "Source")

    def computeTarballOptions(self):
        # Keep in mind that the compression part of tarball generation
        # can be non negligible
        tar = ['tar']
        if self.tarball.endswith("gz"):
            tar.append('-z')
        if self.tarball.endswith("bz2") or self.tarball.endswith("bz"):
            tar.append('-j')
        if self.tarball.endswith("lzma"):
            tar.append('--lzma')
        if self.tarball.endswith("lzop"):
            tar.append('--lzop')
        return tar

    @defer.inlineCallbacks
    def maybeExtractTarball(self):
        if self.tarball:
            tar = self.computeTarballOptions() + ['-xvf', self.tarball]
            res = yield self._Cmd(tar, abandonOnFailure=False)
            if res:  # error with tarball.. erase repo dir and tarball
                yield self._Cmd(["rm", "-f", self.tarball], abandonOnFailure=False)
                yield self.runRmdir(self.repoDir(), abandonOnFailure=False)

    @defer.inlineCallbacks
    def maybeUpdateTarball(self):
        if not self.tarball or self.updateTarballAge is None:
            return
        # tarball path is absolute, so we cannot use worker's stat command
        # stat -c%Y gives mtime in second since epoch
        res = yield self._Cmd(["stat", "-c%Y", self.tarball], collectStdout=True, abandonOnFailure=False)
        if not res:
            tarball_mtime = int(self.lastCommand.stdout)
            yield self._Cmd(["stat", "-c%Y", "."], collectStdout=True)
            now_mtime = int(self.lastCommand.stdout)
            age = now_mtime - tarball_mtime
        if res or age > self.updateTarballAge:
            tar = self.computeTarballOptions() + \
                ['-cvf', self.tarball, ".repo"]
            res = yield self._Cmd(tar, abandonOnFailure=False)
            if res:  # error with tarball.. erase tarball, but don't fail
                yield self._Cmd(["rm", "-f", self.tarball], abandonOnFailure=False)

    # a simple shell script to gather all cleanup tweaks...
    # doing them one by one just complicate the stuff
    # and mess up the stdio log
    def _getCleanupCommand(self):
        """also used by tests for expectations"""
        return textwrap.dedent("""\
            set -v
            if [ -d .repo/manifests ]
            then
                # repo just refuse to run if manifest is messed up
                # so ensure we are in a known state
                cd .repo/manifests
                rm -f .git/index.lock
                git fetch origin
                git reset --hard remotes/origin/%(manifestBranch)s
                git config branch.default.merge %(manifestBranch)s
                cd ..
                ln -sf manifests/%(manifestFile)s manifest.xml
                cd ..
             fi
             repo forall -c rm -f .git/index.lock
             repo forall -c git clean -f -d -x 2>/dev/null
             repo forall -c git reset --hard HEAD 2>/dev/null
             rm -f %(workdir)s/.repo/project.list
             """) % dict(manifestBranch=self.manifestBranch,
                         manifestFile=self.manifestFile,
                         workdir=self.workdir)

    def doCleanup(self):
        command = self._getCleanupCommand()
        return self._Cmd(["bash", "-c", command], abandonOnFailure=False)
