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

from __future__ import annotations

import base64
import json
import os
import random
import re
import shlex
import string
import sys
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import NoReturn

from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import task
from twisted.internet import utils
from twisted.python import log
from twisted.python import runtime
from twisted.python.procutils import which
from twisted.spread import pb

from buildbot.process.results import SUCCESS
from buildbot.process.results import Results
from buildbot.util import bytes2unicode
from buildbot.util import now
from buildbot.util import unicode2bytes
from buildbot.util.eventual import fireEventually

if TYPE_CHECKING:
    from twisted.python.failure import Failure

    from buildbot.util.twisted import InlineCallbacksType


class SourceStamp:
    def __init__(
        self,
        branch: str | None,
        revision: Any,
        patch: tuple[Any, Any],
        repository: str = '',
    ) -> None:
        self.branch = branch
        self.revision = revision
        self.patch = patch
        self.repository = repository


def output(*msg: Any) -> None:
    print(' '.join([str(m) for m in msg]))


class SourceStampExtractor:
    vcexe: str
    baserev: Any
    patch: tuple[Any, Any]

    def getBaseRevision(self) -> defer.Deferred[Any]:
        raise NotImplementedError

    def getPatch(self) -> defer.Deferred[Any]:
        raise NotImplementedError

    def __init__(self, treetop: str, branch: Any, repository: str | None) -> None:
        self.treetop = treetop
        self.repository = repository
        self.branch: Any = branch
        exes = which(self.vcexe)
        if not exes:
            output(f"Could not find executable '{self.vcexe}'.")
            sys.exit(1)
        self.exe = exes[0]

    @defer.inlineCallbacks
    def dovc(self, cmd: list[Any]) -> InlineCallbacksType[bytes]:
        """This accepts the arguments of a command, without the actual
        command itself."""
        env = os.environ.copy()
        env['LC_ALL'] = "C"

        # 'bzr diff' sets rc=1 if there were any differences.
        # cvs does something similar, so don't bother requiring rc=0.
        stdout, _, __ = yield utils.getProcessOutputAndValue(
            self.exe, cmd, env=env, path=self.treetop
        )
        return stdout

    @defer.inlineCallbacks
    def get(self) -> InlineCallbacksType[SourceStamp]:
        """Return a Deferred that fires with a SourceStamp instance."""
        yield self.getBaseRevision()
        yield self.getPatch()
        return self.done()

    def readPatch(self, diff: Any, patchlevel: int) -> None:
        if not diff:
            diff = None
        self.patch = (patchlevel, diff)

    def done(self) -> SourceStamp:
        if not self.repository:
            self.repository = self.treetop
        # TODO: figure out the branch and project too
        ss = SourceStamp(
            bytes2unicode(self.branch), self.baserev, self.patch, repository=self.repository
        )
        return ss


class CVSExtractor(SourceStampExtractor):
    patchlevel = 0
    vcexe = "cvs"

    def getBaseRevision(self) -> defer.Deferred[None]:
        # this depends upon our local clock and the repository's clock being
        # reasonably synchronized with each other. We express everything in
        # UTC because the '%z' format specifier for strftime doesn't always
        # work.
        self.baserev = time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime(now()))
        return defer.succeed(None)

    @defer.inlineCallbacks
    def getPatch(self) -> InlineCallbacksType[None]:
        # the -q tells CVS to not announce each directory as it works
        if self.branch is not None:
            # 'cvs diff' won't take both -r and -D at the same time (it
            # ignores the -r). As best I can tell, there is no way to make
            # cvs give you a diff relative to a timestamp on the non-trunk
            # branch. A bare 'cvs diff' will tell you about the changes
            # relative to your checked-out versions, but I know of no way to
            # find out what those checked-out versions are.
            output("Sorry, CVS 'try' builds don't work with branches")
            sys.exit(1)
        args = ['-q', 'diff', '-u', '-D', self.baserev]
        stdout = yield self.dovc(args)
        self.readPatch(stdout, self.patchlevel)


class SVNExtractor(SourceStampExtractor):
    patchlevel = 0
    vcexe = "svn"

    @defer.inlineCallbacks
    def getBaseRevision(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["status", "-u"])
        self.parseStatus(stdout)

    def parseStatus(self, res: bytes) -> None:
        # svn shows the base revision for each file that has been modified or
        # which needs an update. You can update each file to a different
        # version, so each file is displayed with its individual base
        # revision. It also shows the repository-wide latest revision number
        # on the last line ("Status against revision: \d+").

        # for our purposes, we use the latest revision number as the "base"
        # revision, and get a diff against that. This means we will get
        # reverse-diffs for local files that need updating, but the resulting
        # tree will still be correct. The only weirdness is that the baserev
        # that we emit may be different than the version of the tree that we
        # first checked out.

        # to do this differently would probably involve scanning the revision
        # numbers to find the max (or perhaps the min) revision, and then
        # using that as a base.

        for line in res.split(b"\n"):
            m = re.search(rb'^Status against revision:\s+(\d+)', line)
            if m:
                self.baserev = m.group(1)
                return
        output(b"Could not find 'Status against revision' in SVN output: " + res)
        sys.exit(1)

    @defer.inlineCallbacks
    def getPatch(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["diff", f"-r{self.baserev}"])
        self.readPatch(stdout, self.patchlevel)


class BzrExtractor(SourceStampExtractor):
    patchlevel = 0
    vcexe = "bzr"

    @defer.inlineCallbacks
    def getBaseRevision(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["revision-info", "-rsubmit:"])
        self.get_revision_number(stdout)

    def get_revision_number(self, out: bytes) -> None:
        _, revid = out.split()
        self.baserev = b'revid:' + revid

    @defer.inlineCallbacks
    def getPatch(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["diff", f"-r{self.baserev}.."])
        self.readPatch(stdout, self.patchlevel)


class MercurialExtractor(SourceStampExtractor):
    patchlevel = 1
    vcexe = "hg"

    def _didvc(self, res: tuple[str, str, int], cmd: list[str]) -> str:
        (stdout, stderr, code) = res

        if code:
            cs = ' '.join(['hg', *cmd])
            if stderr:
                stderr = '\n' + stderr.rstrip()
            raise RuntimeError(f"{cs} returned {code} {stderr}")

        return stdout

    @defer.inlineCallbacks
    def getBaseRevision(self) -> InlineCallbacksType[None]:
        upstream = ""
        if self.repository:
            upstream = f"r'{self.repository}'"
        output = ''
        try:
            output = yield self.dovc([
                "log",
                "--template",
                "{node}\\n",
                "-r",
                f"max(::. - outgoing({upstream}))",
            ])
        except RuntimeError:
            # outgoing() will abort if no default-push/default path is
            # configured
            if upstream:
                raise
            # fall back to current working directory parent
            output = yield self.dovc(["log", "--template", "{node}\\n", "-r", "p1()"])
        m = re.search(rb'^(\w+)', output)
        if not m:
            raise RuntimeError(f"Revision {output!r} is not in the right format")
        self.baserev = m.group(0)

    @defer.inlineCallbacks
    def getPatch(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["diff", "-r", self.baserev])
        self.readPatch(stdout, self.patchlevel)


class PerforceExtractor(SourceStampExtractor):
    patchlevel = 0
    vcexe = "p4"

    @defer.inlineCallbacks
    def getBaseRevision(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["changes", "-m1", "..."])
        self.parseStatus(stdout)

    def parseStatus(self, res: bytes) -> None:
        #
        # extract the base change number
        #
        m = re.search(rb'Change (\d+)', res)
        if m:
            self.baserev = m.group(1)
            return

        output(b"Could not find change number in output: " + res)
        sys.exit(1)

    def readPatch(self, diff: Any, patchlevel: int) -> None:
        #
        # extract the actual patch from "diff"
        #
        if not self.branch:
            output("you must specify a branch")
            sys.exit(1)
        mpatch = ""
        found = False
        for line in diff.split("\n"):
            m = re.search('==== //depot/' + self.branch + r'/([\w/\.\d\-_]+)#(\d+) -', line)
            if m:
                mpatch += f"--- {m.group(1)}#{m.group(2)}\n"
                mpatch += f"+++ {m.group(1)}\n"
                found = True
            else:
                mpatch += line
                mpatch += "\n"
        if not found:
            output(b"could not parse patch file")
            sys.exit(1)
        self.patch = (patchlevel, unicode2bytes(mpatch))

    @defer.inlineCallbacks
    def getPatch(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["diff"])
        self.readPatch(stdout, self.patchlevel)


class DarcsExtractor(SourceStampExtractor):
    patchlevel = 1
    vcexe = "darcs"

    @defer.inlineCallbacks
    def getBaseRevision(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["changes", "--context"])
        self.baserev = stdout  # the whole context file

    @defer.inlineCallbacks
    def getPatch(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["diff", "-u"])
        self.readPatch(stdout, self.patchlevel)


class GitExtractor(SourceStampExtractor):
    patchlevel = 1
    vcexe = "git"
    config: dict[bytes, bytes] | None = None

    @defer.inlineCallbacks
    def getBaseRevision(self) -> InlineCallbacksType[None]:
        # If a branch is specified, parse out the rev it points to
        # and extract the local name.
        if self.branch:
            stdout = yield self.dovc(["rev-parse", self.branch])
            self.override_baserev(stdout)
            yield self.extractLocalBranch()
            return
        stdout = yield self.dovc(["branch", "--no-color", "-v", "--no-abbrev"])
        yield self.parseStatus(stdout)

    # remove remote-prefix from self.branch (assumes format <prefix>/<branch>)
    # this uses "git remote" to retrieve all configured remote names
    @defer.inlineCallbacks
    def extractLocalBranch(self) -> InlineCallbacksType[None]:
        if '/' in self.branch:
            stdout = yield self.dovc(["remote"])
            self.fixBranch(stdout)

    # strip remote prefix from self.branch
    def fixBranch(self, remotes: bytes) -> None:
        for l in bytes2unicode(remotes).split("\n"):
            r = l.strip()
            if r and self.branch.startswith(r + "/"):
                self.branch = self.branch[len(r) + 1 :]
                break

    @defer.inlineCallbacks
    def readConfig(self) -> InlineCallbacksType[dict[bytes, bytes]]:
        if self.config:
            return self.config
        stdout = yield self.dovc(["config", "-l"])
        return self.parseConfig(stdout)

    def parseConfig(self, res: bytes) -> dict[bytes, bytes]:
        self.config = {}
        for l in res.split(b"\n"):
            if l.strip():
                parts = l.strip().split(b"=", 2)
                if len(parts) < 2:
                    parts.append(b'true')
                self.config[parts[0]] = parts[1]
        return self.config

    @defer.inlineCallbacks
    def parseTrackingBranch(self, res: Any) -> InlineCallbacksType[None]:
        # If we're tracking a remote, consider that the base.
        remote = self.config.get(b"branch." + self.branch + b".remote")  # type: ignore[union-attr]
        ref = self.config.get(b"branch." + self.branch + b".merge")  # type: ignore[union-attr]
        if remote and ref:
            remote_branch = ref.split(b"/", 2)[-1]
            baserev = remote + b"/" + remote_branch
        else:
            baserev = b"master"

        stdout = yield self.dovc(["rev-parse", baserev])
        self.override_baserev(stdout)

    def override_baserev(self, res: Any) -> None:
        self.baserev = bytes2unicode(res).strip()

    @defer.inlineCallbacks
    def parseStatus(self, res: bytes) -> InlineCallbacksType[None]:
        # The current branch is marked by '*' at the start of the
        # line, followed by the branch name and the SHA1.
        #
        # Branch names may contain pretty much anything but whitespace.
        m = re.search(rb'^\* (\S+)\s+([0-9a-f]{40})', res, re.MULTILINE)
        if m:
            self.baserev = m.group(2)
            self.branch = m.group(1)
            config = yield self.readConfig()
            yield self.parseTrackingBranch(config)
            return
        output(b"Could not find current GIT branch: " + res)
        sys.exit(1)

    @defer.inlineCallbacks
    def getPatch(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc([
            "diff",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--no-textconv",
            "--no-ext-diff",
            self.baserev,
        ])
        self.readPatch(stdout, self.patchlevel)


class MonotoneExtractor(SourceStampExtractor):
    patchlevel = 0
    vcexe = "mtn"

    @defer.inlineCallbacks
    def getBaseRevision(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["automate", "get_base_revision_id"])
        self.parseStatus(stdout)

    def parseStatus(self, output: Any) -> None:
        hash = output.strip()
        if len(hash) != 40:
            self.baserev = None
        self.baserev = hash

    @defer.inlineCallbacks
    def getPatch(self) -> InlineCallbacksType[None]:
        stdout = yield self.dovc(["diff"])
        self.readPatch(stdout, self.patchlevel)


def getSourceStamp(
    vctype: str | None, treetop: str, branch: str | None = None, repository: str | None = None
) -> defer.Deferred[SourceStamp]:
    if vctype == "cvs":
        cls: type[SourceStampExtractor] = CVSExtractor
    elif vctype == "svn":
        cls = SVNExtractor
    elif vctype == "bzr":
        cls = BzrExtractor
    elif vctype == "hg":
        cls = MercurialExtractor
    elif vctype == "p4":
        cls = PerforceExtractor
    elif vctype == "darcs":
        cls = DarcsExtractor
    elif vctype == "git":
        cls = GitExtractor
    elif vctype == "mtn":
        cls = MonotoneExtractor
    elif vctype == "none":
        return defer.succeed(SourceStamp("", "", (1, ""), ""))
    else:
        output(f"unknown vctype '{vctype}'")
        sys.exit(1)
    return cls(treetop, branch, repository).get()


def ns(s: str) -> str:
    return f"{len(s)}:{s},"


def createJobfile(
    jobid: str,
    branch: str,
    baserev: str,
    patch_level: Any,
    patch_body: Any,
    repository: str,
    project: Any,
    who: Any,
    comment: Any,
    builderNames: Any,
    properties: Any,
) -> str:
    # Determine job file version from provided arguments
    try:
        bytes2unicode(patch_body)
        version = 5
    except UnicodeDecodeError:
        version = 6

    job = ""
    job += ns(str(version))
    job_dict = {
        'jobid': jobid,
        'branch': branch,
        'baserev': str(baserev),
        'patch_level': patch_level,
        'repository': repository,
        'project': project,
        'who': who,
        'comment': comment,
        'builderNames': builderNames,
        'properties': properties,
    }
    if version > 5:
        job_dict['patch_body_base64'] = bytes2unicode(base64.b64encode(patch_body))
    else:
        job_dict['patch_body'] = bytes2unicode(patch_body)

    job += ns(json.dumps(job_dict))
    return job


def getTopdir(topfile: str, start: str | None = None) -> str:
    """walk upwards from the current directory until we find this topfile"""
    if not start:
        start = os.getcwd()
    here = start
    toomany = 20
    while toomany > 0:
        if os.path.exists(os.path.join(here, topfile)):
            return here
        next = os.path.dirname(here)
        if next == here:
            break  # we've hit the root
        here = next
        toomany -= 1
    output(f"Unable to find topfile '{topfile}' anywhere from {start} upwards")
    sys.exit(1)


class RemoteTryPP(protocol.ProcessProtocol):
    def __init__(self, job: str) -> None:
        self.job = job
        self.d: defer.Deferred[tuple[int | None, int | None]] = defer.Deferred()

    def connectionMade(self) -> None:
        self.transport.write(unicode2bytes(self.job))  # type: ignore[union-attr]
        self.transport.closeStdin()  # type: ignore[union-attr]

    def outReceived(self, data: bytes) -> None:
        sys.stdout.write(bytes2unicode(data))

    def errReceived(self, data: bytes) -> None:
        sys.stderr.write(bytes2unicode(data))

    def processEnded(self, reason: Failure) -> None:
        sig = reason.value.signal
        rc = reason.value.exitCode
        if sig is not None or rc != 0:
            self.d.errback(RuntimeError(f"remote 'buildbot tryserver' failed: sig={sig}, rc={rc}"))
            return
        self.d.callback((sig, rc))


class FakeBuildSetStatus:
    def callRemote(self, name: str) -> defer.Deferred[list[Any]]:
        if name == "getBuildRequests":
            return defer.succeed([])
        raise NotImplementedError()


class Try(pb.Referenceable):
    buildsetStatus: Any = None
    quiet: bool = False
    printloop: task.LoopingCall | None = None

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.connect = self.getopt('connect')
        if self.connect not in ['ssh', 'pb']:
            output("you must specify a connect style: ssh or pb")
            sys.exit(1)
        self.builderNames = self.getopt('builders')
        self.project = self.getopt('project', '')
        self.who = self.getopt('who')
        self.comment = self.getopt('comment')

    def getopt(self, config_name: str, default: Any = None) -> Any:
        value = self.config.get(config_name)
        if value is None or value == []:
            value = default
        return value

    def createJob(self) -> defer.Deferred[Any]:
        # returns a Deferred which fires when the job parameters have been
        # created

        # generate a random (unique) string. It would make sense to add a
        # hostname and process ID here, but a) I suspect that would cause
        # windows portability problems, and b) really this is good enough
        self.bsid = f"{time.time()}-{random.randint(0, 1000000)}"

        # common options
        branch = self.getopt("branch")

        difffile = self.config.get("diff")
        if difffile:
            baserev = self.config.get("baserev")
            if difffile == "-":
                diff = sys.stdin.read()
            else:
                with open(difffile, "rb") as f:
                    diff = f.read()
            if not diff:
                diff = None
            patch = (self.config['patchlevel'], diff)
            ss = SourceStamp(branch, baserev, patch, repository=self.getopt("repository"))
            d = defer.succeed(ss)
        else:
            vc = self.getopt("vc")
            if vc in ("cvs", "svn"):
                # we need to find the tree-top
                topdir = self.getopt("topdir")
                if topdir:
                    treedir = os.path.expanduser(topdir)
                else:
                    topfile = self.getopt("topfile")
                    if topfile:
                        treedir = getTopdir(topfile)
                    else:
                        output("Must specify topdir or topfile.")
                        sys.exit(1)
            else:
                treedir = os.getcwd()
            d = getSourceStamp(vc, treedir, branch, self.getopt("repository"))
        d.addCallback(self._createJob_1)
        return d

    def _createJob_1(self, ss: SourceStamp) -> None:
        self.sourcestamp = ss
        patchlevel, diff = ss.patch
        if diff is None:
            output("WARNING: There is no patch to try, diff is empty.")

        if self.connect == "ssh":
            revspec = ss.revision
            if revspec is None:
                revspec = ""
            self.jobfile = createJobfile(
                self.bsid,
                ss.branch or "",
                revspec,
                patchlevel,
                diff,
                ss.repository,
                self.project,
                self.who,
                self.comment,
                self.builderNames,
                self.config.get('properties', {}),
            )

    def fakeDeliverJob(self) -> defer.Deferred[bool]:
        # Display the job to be delivered, but don't perform delivery.
        ss = self.sourcestamp
        output(
            f"Job:\n\tRepository: {ss.repository}\n\tProject: {self.project}\n\tBranch: "
            f"{ss.branch}\n\tRevision: {ss.revision}\n\tBuilders: "
            f"{self.builderNames}\n{ss.patch[1]}"
        )
        self.buildsetStatus = FakeBuildSetStatus()
        return defer.succeed(True)

    def deliver_job_ssh(self) -> defer.Deferred[tuple[int | None, int | None]]:
        tryhost = self.getopt("host")
        tryport = self.getopt("port")
        tryuser = self.getopt("username")
        trydir = self.getopt("jobdir")
        buildbotbin = self.getopt("buildbotbin")
        ssh_command = self.getopt("ssh")
        if not ssh_command:
            ssh_commands = which("ssh")
            if not ssh_commands:
                raise RuntimeError(
                    "couldn't find ssh executable, make sure it is available in the PATH"
                )

            argv = [ssh_commands[0]]
        else:
            # Split the string on whitespace to allow passing options in
            # ssh command too, but preserving whitespace inside quotes to
            # allow using paths with spaces in them which is common under
            # Windows. And because Windows uses backslashes in paths, we
            # can't just use shlex.split there as it would interpret them
            # specially, so do it by hand.
            if runtime.platformType == 'win32':
                # Note that regex here matches the arguments, not the
                # separators, as it's simpler to do it like this. And then we
                # just need to get all of them together using the slice and
                # also remove the quotes from those that were quoted.
                argv = [
                    string.strip(a, '"')  # type: ignore[attr-defined]
                    for a in re.split(r"""([^" ]+|"[^"]+")""", ssh_command)[1::2]
                ]
            else:
                # Do use standard tokenization logic under POSIX.
                argv = shlex.split(ssh_command)

        if tryuser:
            argv += ["-l", tryuser]

        if tryport:
            argv += ["-p", tryport]

        argv += [tryhost, buildbotbin, "tryserver", "--jobdir", trydir]
        pp = RemoteTryPP(self.jobfile)
        reactor.spawnProcess(pp, argv[0], argv, os.environ)  # type: ignore[attr-defined]
        d = pp.d
        return d

    @defer.inlineCallbacks
    def deliver_job_pb(self) -> InlineCallbacksType[None]:
        user = self.getopt("username")
        passwd = self.getopt("passwd")
        master = self.getopt("master")
        tryhost, tryport = master.split(":")
        tryport = int(tryport)
        f = pb.PBClientFactory()
        d = f.login(credentials.UsernamePassword(unicode2bytes(user), unicode2bytes(passwd)))
        reactor.connectTCP(tryhost, tryport, f)  # type: ignore[attr-defined]
        remote = yield d

        ss = self.sourcestamp
        output("Delivering job; comment=", self.comment)

        self.buildsetStatus = yield remote.callRemote(
            "try",
            ss.branch,
            ss.revision,
            ss.patch,
            ss.repository,
            self.project,
            self.builderNames,
            self.who,
            self.comment,
            self.config.get('properties', {}),
        )

    def deliverJob(self) -> defer.Deferred[Any]:
        # returns a Deferred that fires when the job has been delivered
        if self.connect == "ssh":
            return self.deliver_job_ssh()
        if self.connect == "pb":
            return self.deliver_job_pb()
        raise RuntimeError(f"unknown connecttype '{self.connect}', should be 'ssh' or 'pb'")

    def getStatus(self) -> defer.Deferred[Any] | None:
        # returns a Deferred that fires when the builds have finished, and
        # may emit status messages while we wait
        wait = bool(self.getopt("wait"))
        if not wait:
            output("not waiting for builds to finish")
        elif self.connect == "ssh":
            output("waiting for builds with ssh is not supported")
        else:
            self.running: defer.Deferred[int] = defer.Deferred()
            if not self.buildsetStatus:
                output("try scheduler on the master does not have the builder configured")
                return None

            self._getStatus_1()  # note that we don't wait for the returned Deferred
            if bool(self.config.get("dryrun")):
                self.statusDone()
            return self.running
        return None

    @defer.inlineCallbacks
    def _getStatus_1(self) -> InlineCallbacksType[None]:
        # gather the set of BuildRequests
        brs = yield self.buildsetStatus.callRemote("getBuildRequests")

        self.builderNames = []
        self.buildRequests: dict[Any, Any] = {}

        # self.builds holds the current BuildStatus object for each one
        self.builds: dict[Any, Any] = {}

        # self.outstanding holds the list of builderNames which haven't
        # finished yet
        self.outstanding: list[Any] = []

        # self.results holds the list of build results. It holds a tuple of
        # (result, text)
        self.results: dict[Any, list[Any]] = {}

        # self.currentStep holds the name of the Step that each build is
        # currently running
        self.currentStep: dict[Any, Any] = {}

        # self.ETA holds the expected finishing time (absolute time since
        # epoch)
        self.ETA: dict[Any, Any] = {}

        for n, br in brs:
            self.builderNames.append(n)
            self.buildRequests[n] = br
            self.builds[n] = None
            self.outstanding.append(n)
            self.results[n] = [None, None]
            self.currentStep[n] = None
            self.ETA[n] = None
            # get new Builds for this buildrequest. We follow each one until
            # it finishes or is interrupted.
            br.callRemote("subscribe", self)

        # now that those queries are in transit, we can start the
        # display-status-every-30-seconds loop
        if not self.getopt("quiet"):
            self.printloop = task.LoopingCall(self.printStatus)
            self.printloop.start(3, now=False)

    # these methods are invoked by the status objects we've subscribed to

    def remote_newbuild(self, bs: Any, builderName: Any) -> None:
        if self.builds[builderName]:
            self.builds[builderName].callRemote("unsubscribe", self)
        self.builds[builderName] = bs
        bs.callRemote("subscribe", self, 20)
        d = bs.callRemote("waitUntilFinished")
        d.addCallback(self._build_finished, builderName)

    def remote_stepStarted(self, buildername: Any, build: Any, stepname: Any, step: Any) -> None:
        self.currentStep[buildername] = stepname

    def remote_stepFinished(
        self, buildername: Any, build: Any, stepname: Any, step: Any, results: Any
    ) -> None:
        pass

    def remote_buildETAUpdate(self, buildername: Any, build: Any, eta: float) -> None:
        self.ETA[buildername] = now() + eta

    @defer.inlineCallbacks
    def _build_finished(self, bs: Any, builderName: Any) -> InlineCallbacksType[None]:
        # we need to collect status from the newly-finished build. We don't
        # remove the build from self.outstanding until we've collected
        # everything we want.
        self.builds[builderName] = None
        self.ETA[builderName] = None
        self.currentStep[builderName] = "finished"

        self.results[builderName][0] = yield bs.callRemote("getResults")
        self.results[builderName][1] = yield bs.callRemote("getText")

        self.outstanding.remove(builderName)
        if not self.outstanding:
            self.statusDone()

    def printStatus(self) -> None:
        try:
            names = sorted(self.buildRequests.keys())
            for n in names:
                if n not in self.outstanding:
                    # the build is finished, and we have results
                    code, text = self.results[n]
                    t = Results[code]
                    if text:
                        t += f' ({" ".join(text)})'
                elif self.builds[n]:
                    t = self.currentStep[n] or "building"
                    if self.ETA[n]:
                        t += f" [ETA {self.ETA[n] - now()}s]"
                else:
                    t = "no build"
                self.announce(f"{n}: {t}")
            self.announce("")
        except Exception:
            log.err(None, "printing status")

    def statusDone(self) -> None:
        if self.printloop:
            self.printloop.stop()
            self.printloop = None
        output("All Builds Complete")
        # TODO: include a URL for all failing builds
        names = sorted(self.buildRequests.keys())
        happy = True
        for n in names:
            code, text = self.results[n]
            t = f"{n}: {Results[code]}"
            if text:
                t += f' ({" ".join(text)})'
            output(t)
            if code != SUCCESS:
                happy = False

        if happy:
            self.exitcode = 0
        else:
            self.exitcode = 1
        self.running.callback(self.exitcode)

    @defer.inlineCallbacks
    def getAvailableBuilderNames(self) -> InlineCallbacksType[None]:
        # This logs into the master using the PB protocol to
        # get the names of the configured builders that can
        # be used for the --builder argument
        if self.connect == "pb":
            user = self.getopt("username")
            passwd = self.getopt("passwd")
            master = self.getopt("master")
            tryhost, tryport = master.split(":")
            tryport = int(tryport)
            f = pb.PBClientFactory()
            d = f.login(credentials.UsernamePassword(unicode2bytes(user), unicode2bytes(passwd)))
            reactor.connectTCP(tryhost, tryport, f)  # type: ignore[attr-defined]
            remote = yield d
            buildernames = yield remote.callRemote("getAvailableBuilderNames")

            output("The following builders are available for the try scheduler: ")
            for buildername in buildernames:
                output(buildername)

            yield remote.broker.transport.loseConnection()
            return
        if self.connect == "ssh":
            output("Cannot get available builders over ssh.")
            sys.exit(1)
        raise RuntimeError(f"unknown connecttype '{self.connect}', should be 'pb'")

    def announce(self, message: str) -> None:
        if not self.quiet:
            output(message)

    @defer.inlineCallbacks
    def run_impl(self) -> InlineCallbacksType[None]:
        output(f"using '{self.connect}' connect method")
        self.exitcode = 0

        # we can't do spawnProcess until we're inside reactor.run(), so force asynchronous execution
        yield fireEventually(None)

        try:
            if bool(self.config.get("get-builder-names")):
                yield self.getAvailableBuilderNames()
            else:
                yield self.createJob()
                yield self.announce("job created")  # type: ignore[func-returns-value]
                if bool(self.config.get("dryrun")):
                    yield self.fakeDeliverJob()
                else:
                    yield self.deliverJob()
                yield self.announce("job has been delivered")  # type: ignore[func-returns-value]
                yield self.getStatus()

            if not bool(self.config.get("dryrun")):
                yield self.cleanup()  # type: ignore[func-returns-value]
        except SystemExit as e:
            self.exitcode = e.code  # type: ignore[assignment]
        except Exception as e:
            log.err(e)
            raise

    def run(self) -> NoReturn:
        d = self.run_impl()
        d.addCallback(lambda res: reactor.stop())  # type: ignore[call-overload,attr-defined]

        reactor.run()  # type: ignore[attr-defined]
        sys.exit(self.exitcode)

    def trapSystemExit(self, why: Failure) -> None:
        why.trap(SystemExit)
        self.exitcode = why.value.code

    def cleanup(self, res: Any = None) -> None:
        if self.buildsetStatus:
            self.buildsetStatus.broker.transport.loseConnection()
