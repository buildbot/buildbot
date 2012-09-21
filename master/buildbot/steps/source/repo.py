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

import re
import textwrap

from twisted.internet import defer, reactor

from buildbot.process import buildstep
from buildbot.steps.source.base import Source

def default_sync_all_branches(properties):
    # in case of manifest_override, we have no other choice to download all branches
    # each project can indeed point on arbitrary commit
    return properties.getProperty("manifest_override_url","")!=""

def default_update_tarball(properties,sync_all_branch_done):
    # dont create a too big tarball in case we synched all branches
    if not sync_all_branch_done:
        return 7*24.0*3600.0
    return None

class Repo(Source):
    """ Class for Repo with all the smarts """
    name='repo'
    renderables = ["manifest_url","manifest_branch","manifest_file", "tarball", "jobs"]

    parse_download_re = (re.compile(r"repo download ([^ ]+) ([0-9]+/[0-9]+)"),
                          re.compile(r"([^ ]+) ([0-9]+/[0-9]+)"),
                          re.compile(r"([^ ]+)/([0-9]+/[0-9]+)"),
                         )
    ref_not_found_re = re.compile(r"fatal: Couldn't find remote ref")
    cherry_pick_error_re = re.compile(r"|".join([r"Automatic cherry-pick failed",
                                                r"error: "
                                                r"fatal: "
                                                r"possibly due to conflict resolution."]))
    re_change = re.compile(r".* refs/changes/\d\d/(\d+)/(\d+) -> FETCH_HEAD$")
    re_head = re.compile(r"^HEAD is now at ([0-9a-f]+)...")
    mirror_sync_retry = 10 # number of retries, if we detect mirror desynchronization
    mirror_sync_sleep = 60 # wait 1min between retries (thus default total retry time is 10min)
    def __init__(self,
                 manifest_url=None,
                 manifest_branch="master",
                 manifest_file="default.xml",
                 tarball=None,
                 jobs=None,
                 sync_all_branches=default_sync_all_branches,
                 update_tarball=default_update_tarball,
                 **kwargs):
        """
        @type  manifest_url: string
        @param manifest_url: The URL which points at the repo manifests repository.

        @type  manifest_branch: string
        @param manifest_branch: The manifest branch to check out by default.

        @type  manifest_file: string
        @param manifest_file: The manifest to use for sync.

        @type sync_all_branches: lambda properties: bool.
        @param sync_all_branches: returns the boolean we must synchronize all branches.

        @type update_tarball: lambda (properties,bool) : float
        @param update_tarball: function to determine the update tarball policy,
	       		       given properties, and boolean indicating whether
			       the last repo sync was on all branches
                               Returns: max age of tarball in seconds, or None, if we
                               want to skip tarball update

        """
        self.manifest_url = manifest_url
        self.manifest_branch = manifest_branch
        self.manifest_file = manifest_file
        self.tarball = tarball
        self.jobs = jobs
        def copy_callable(param_name,f):
            if not callable(f):
                raise ValueError("%s must be callable,but is of type %s"%(param_name,type(f)))
            setattr(self, param_name, f)
        copy_callable("sync_all_branches",sync_all_branches)
        copy_callable("update_tarball",update_tarball)
        Source.__init__(self, **kwargs)

        assert self.manifest_url is not None
        self.addFactoryArguments(manifest_url=manifest_url,
                                 manifest_branch=manifest_branch,
                                 manifest_file=manifest_file,
                                 tarball=tarball,
                                 sync_all_branches=sync_all_branches,
                                 update_tarball=update_tarball,
                                 )

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return changes[-1].revision

    def parseDownloadProperty(self, s):
        """
         lets try to be nice in the format we want
         can support several instances of "repo download proj number/patch" (direct copy paste from gerrit web site)
         or several instances of "proj number/patch" (simpler version)
         This feature allows integrator to build with several pending interdependant changes.
         returns list of repo downloads sent to the buildslave
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

    def buildDownloadList(self):
        """taken the changesource and forcebuild property,
        build the repo download command to send to the slave
        making this a defereable allow config to tweak this
        in order to e.g. manage dependancies
        """
        downloads = self.build.getProperty("repo_downloads", [])

        # download patches based on GerritChangeSource events
        for change in self.build.allChanges():
            if (change.properties.has_key("event.type") and
                change.properties["event.type"] == "patchset-created"):
                downloads.append("%s %s/%s"% (change.properties["event.change.project"],
                                                 change.properties["event.change.number"],
                                                 change.properties["event.patchSet.number"]))

        # download patches based on web site forced build properties:
        # "repo_d", "repo_d0", .., "repo_d9"
        # "repo_download", "repo_download0", .., "repo_download9"
        for propName in ["repo_d"] + ["repo_d%d" % i for i in xrange(0,10)] + \
          ["repo_download"] + ["repo_download%d" % i for i in xrange(0,10)]:
            s = self.build.getProperty(propName)
            if s is not None:
                downloads.extend(self.parseDownloadProperty(s))

        self.repo_downloads = downloads
        if downloads:
            self.setProperty("repo_downloads", downloads, "repo step")
        return defer.succeed(None)

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
        for download in self.repo_downloads:
            project, ch_ps = download.split(" ")[-2:]
            if ( self.manifest_url.endswith("/"+project) or
                 self.manifest_url.endswith("/"+project+".git")):
                ch, ps = map(int, ch_ps.split("/"))
                branch = "refs/changes/%02d/%d/%d"%(ch%100, ch, ps)
                manifest_related_downloads.append(
                    ["git", "fetch", self.manifest_url, branch])
                manifest_related_downloads.append(
                    ["git", "cherry-pick", "FETCH_HEAD"])
            else:
                manifest_unrelated_downloads.append(download)
        self.repo_downloads = manifest_unrelated_downloads
        self.manifest_downloads = manifest_related_downloads

    def _repoCmd(self, command, abandonOnFailure=True, **kwargs):
        return self._Cmd(["repo"]+command, abandonOnFailure=abandonOnFailure, **kwargs)

    def _Cmd(self, command, abandonOnFailure=True,workdir=None, **kwargs):
        if workdir is None:
            workdir = self.workdir
        self.cmd = cmd = buildstep.RemoteShellCommand(workdir, command,
                                                      env=self.env,
                                                      logEnviron=self.logEnviron,
                                                      timeout=self.timeout,  **kwargs)
        # does not make sense to logEnviron for each command (just for first)
        self.logEnviron = False
        cmd.useLog(self.stdio_log, False)
        self.stdio_log.addHeader("Starting command: %s\n" % (" ".join(command), ))
        self.step_status.setText(["%s"%(" ".join(command[:2]))])
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if abandonOnFailure and cmd.didFail():
                self.step_status.setText(["repo failed at: %s"%(" ".join(command[:2]))])
                self.stdio_log.addStderr("Source step failed while running command %s\n" % cmd)
                raise buildstep.BuildStepFailed()
            return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d
    def repoDir(self):
        return self.build.pathmodule.join(self.workdir, ".repo")
    def sourcedirIsUpdateable(self):
        return self.pathExists(self.repoDir())

    def startVC(self, branch, revision, patch):
        d = self.doStartVC()
        d.addErrback(self.failed)

    @defer.inlineCallbacks
    def doStartVC(self):
        self.manifest_override_url = self.build.getProperty("manifest_override_url")
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        # run our setup callbacks from the start, we'll use the results later
        properties = self.build.getProperties()
        self.will_sync_all_branches = self.sync_all_branches(properties)
        if self.update_tarball is not None:
            time_to_update = self.update_tarball(properties,
                                                 self.will_sync_all_branches)
            self.tarball_updating_age = time_to_update

        yield self.buildDownloadList()

        self.filterManifestPatches()

        if self.repo_downloads:
            self.stdio_log.addHeader("will download:\n" + "repo download "+ "\nrepo download ".join(self.repo_downloads) + "\n")

        self.willRetryInCaseOfFailure = True

        d = self.doRepoSync()
        def maybeRetry(why):
            # in case the tree was corrupted somehow because of previous build
            # we clobber one time, and retry everything
            if why.check(buildstep.BuildStepFailed) and self.willRetryInCaseOfFailure:
                self.stdio_log.addStderr("got issue at first try:\n" +str(why)+
                                         "\nRetry after clobber...")
                return self.doRepoSync(forceClobber=True)
            return why # propagate to self.failed
        d.addErrback(maybeRetry)
        yield d
        yield self.maybeUpdateTarball()

        # starting from here, clobbering will not help
        yield self.doRepoDownloads()
        self.setStatus(self.cmd, 0)
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
                             '-u', self.manifest_url,
                             '-b', self.manifest_branch,
                             '-m', self.manifest_file])

        if self.manifest_override_url:
            self.stdio_log.addHeader("overriding manifest with %s\n" %(self.manifest_override_url))
            local_file = yield self.pathExists(self.build.pathmodule.join(self.workdir,
                                                                  self.manifest_override_url))
            if local_file:
                yield self._Cmd(["cp", "-f", self.manifest_override_url, "manifest_override.xml"])
            else:
                yield self._Cmd(["wget", self.manifest_override_url, "-O", "manifest_override.xml"])
            yield self._Cmd(["ln", "-sf", "../manifest_override.xml", "manifest.xml"],
                            workdir=self.build.pathmodule.join(self.workdir,".repo"))

        for command in self.manifest_downloads:
            yield self._Cmd(command, workdir=self.build.pathmodule.join(self.workdir,".repo","manifests"))

        command = ['sync']
        if self.jobs:
          command.append('-j' + str(self.jobs))
        if not self.will_sync_all_branches:
            command.append('-c')
        self.step_status.setText(["repo sync"])
        self.stdio_log.addHeader("synching manifest %s from branch %s from %s\n"
                                 % (self.manifest_file, self.manifest_branch, self.manifest_url))
        yield self._repoCmd(command)

        command = ['manifest', '-r', '-o', 'manifest-original.xml']
        yield self._repoCmd(command)

    # check whether msg matches one of the
    # compiled regexps in self.re_error_messages
    def _findErrorMessages(self, error_re):
        for logname in ['stderr', 'stdout']:
            if not hasattr(self.cmd, logname):
                continue
            msg = getattr(self.cmd, logname)
            if not (re.search(error_re,msg) is None):
                return True
        return False

    def _sleep(self, delay):
        d = defer.Deferred()
        reactor.callLater(delay,d.callback,1)
        return d

    @defer.inlineCallbacks
    def doRepoDownloads(self):
        self.repo_downloaded = ""
        for download in self.repo_downloads:
            command = ['download'] + download.split(' ')
            self.stdio_log.addHeader("downloading changeset %s\n"
                                     % (download))

            retry = self.mirror_sync_retry + 1
            while retry > 0:
                yield self._repoCmd(command, abandonOnFailure = False,
                                    collectStdout=True, collectStderr=True)
                if not self._findErrorMessages(self.ref_not_found_re):
                    break
                retry -=1
                self.stdio_log.addStderr("failed downloading changeset %s\n"% (download))
                self.stdio_log.addHeader("wait one minute for mirror sync\n")
                yield self._sleep(self.mirror_sync_sleep)

            if retry == 0:
                self.step_status.setText(["repo: change %s does not exist"%download])
                self.step_status.setText2(["repo: change %s does not exist"%download])
                raise buildstep.BuildStepFailed()

            if self.cmd.didFail() or self._findErrorMessages(self.cherry_pick_error_re):
                # cherry pick error! We create a diff with status current workdir
                # in stdout, which reveals the merge errors and exit
                command = ['forall','-c' ,'git' ,'diff', 'HEAD']
                yield self._repoCmd(command, abandonOnFailure = False)
                self.step_status.setText(["download failed: %s"%download])
                raise buildstep.BuildStepFailed()

            if hasattr(self.cmd, 'stderr'):
                lines = self.cmd.stderr.split("\n")
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
            tar = self.computeTarballOptions() + [ '-xvf', self.tarball ]
            res = yield self._Cmd(tar, abandonOnFailure=False)
            if res: # error with tarball.. erase repo dir and tarball
                yield self._Cmd(["rm", "-f", self.tarball], abandonOnFailure=False)
                yield self.runRmdir(self.repoDir(), abandonOnFailure=False)

    @defer.inlineCallbacks
    def maybeUpdateTarball(self):
        if not self.tarball or self.tarball_updating_age is None:
            return
        # tarball path is absolute, so we cannot use slave's stat command
        # stat -c%Y gives mtime in second since epoch
        res = yield self._Cmd(["stat", "-c%Y", self.tarball], collectStdout=True, abandonOnFailure=False)
        if not res:
            tarball_mtime = int(self.cmd.stdout)
            yield self._Cmd(["stat", "-c%Y", "." ],collectStdout=True)
            now_mtime = int(self.cmd.stdout)
            age = now_mtime - tarball_mtime
        if res or age > self.tarball_updating_age:
            tar = self.computeTarballOptions() + [ '-cvf', self.tarball,".repo"]
            res = yield self._Cmd(tar, abandonOnFailure=False)
            if res: # error with tarball.. erase tarball, but dont fail
                yield self._Cmd(["rm", "-f", self.tarball], abandonOnFailure=False)


    # a simple shell script to gather all cleanup tweaks...
    # doing them one by one just complicate the stuff
    # and messup the stdio log
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
                git reset --hard remotes/origin/%(manifest_branch)s
                git config branch.default.merge %(manifest_branch)s
                cd ..
                ln -sf manifests/%(manifest_file)s manifest.xml
                cd ..
             fi
             repo forall -c rm -f .git/index.lock
             repo forall -c git clean -f -d -x 2>/dev/null
             repo forall -c git reset --hard HEAD 2>/dev/null
	     rm -f %(workdir)s/.repo/project.list
             """) % self.__dict__
    def doCleanup(self):
        command = self._getCleanupCommand()
        return self._Cmd(["bash", "-c", command],abandonOnFailure=False)
