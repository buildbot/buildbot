# -*- test-case-name: buildbot.test.test_scheduler,buildbot.test.test_vc -*-

import sys, os, re, time, random
from twisted.internet import utils, protocol, defer, reactor, task
from twisted.spread import pb
from twisted.cred import credentials
from twisted.python import log
from twisted.python.procutils import which

from buildbot.sourcestamp import SourceStamp
from buildbot.scripts import runner
from buildbot.util import now
from buildbot.status import builder

class SourceStampExtractor:

    def __init__(self, treetop, branch):
        self.treetop = treetop
        self.branch = branch
        self.exe = which(self.vcexe)[0]

    def dovc(self, cmd):
        """This accepts the arguments of a command, without the actual
        command itself."""
        env = os.environ.copy()
        env['LC_ALL'] = "C"
        d = utils.getProcessOutputAndValue(self.exe, cmd, env=env,
                                           path=self.treetop)
        d.addCallback(self._didvc, cmd)
        return d
    def _didvc(self, res, cmd):
        (stdout, stderr, code) = res
        # 'bzr diff' sets rc=1 if there were any differences. tla, baz, and
        # cvs do something similar, so don't bother requring rc=0.
        return stdout

    def get(self):
        """Return a Deferred that fires with a SourceStamp instance."""
        d = self.getBaseRevision()
        d.addCallback(self.getPatch)
        d.addCallback(self.done)
        return d
    def readPatch(self, res, patchlevel):
        self.patch = (patchlevel, res)
    def done(self, res):
        # TODO: figure out the branch too
        ss = SourceStamp(self.branch, self.baserev, self.patch)
        return ss

class CVSExtractor(SourceStampExtractor):
    patchlevel = 0
    vcexe = "cvs"
    def getBaseRevision(self):
        # this depends upon our local clock and the repository's clock being
        # reasonably synchronized with each other. We express everything in
        # UTC because the '%z' format specifier for strftime doesn't always
        # work.
        self.baserev = time.strftime("%Y-%m-%d %H:%M:%S +0000",
                                     time.gmtime(now()))
        return defer.succeed(None)

    def getPatch(self, res):
        # the -q tells CVS to not announce each directory as it works
        if self.branch is not None:
            # 'cvs diff' won't take both -r and -D at the same time (it
            # ignores the -r). As best I can tell, there is no way to make
            # cvs give you a diff relative to a timestamp on the non-trunk
            # branch. A bare 'cvs diff' will tell you about the changes
            # relative to your checked-out versions, but I know of no way to
            # find out what those checked-out versions are.
            raise RuntimeError("Sorry, CVS 'try' builds don't work with "
                               "branches")
        args = ['-q', 'diff', '-u', '-D', self.baserev]
        d = self.dovc(args)
        d.addCallback(self.readPatch, self.patchlevel)
        return d

class SVNExtractor(SourceStampExtractor):
    patchlevel = 0
    vcexe = "svn"

    def getBaseRevision(self):
        d = self.dovc(["status", "-u"])
        d.addCallback(self.parseStatus)
        return d
    def parseStatus(self, res):
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

        for line in res.split("\n"):
            m = re.search(r'^Status against revision:\s+(\d+)', line)
            if m:
                self.baserev = int(m.group(1))
                return
        raise IndexError("Could not find 'Status against revision' in "
                         "SVN output: %s" % res)
    def getPatch(self, res):
        d = self.dovc(["diff", "-r%d" % self.baserev])
        d.addCallback(self.readPatch, self.patchlevel)
        return d

class BazExtractor(SourceStampExtractor):
    patchlevel = 1
    vcexe = "baz"
    def getBaseRevision(self):
        d = self.dovc(["tree-id"])
        d.addCallback(self.parseStatus)
        return d
    def parseStatus(self, res):
        tid = res.strip()
        slash = tid.index("/")
        dd = tid.rindex("--")
        self.branch = tid[slash+1:dd]
        self.baserev = tid[dd+2:]
    def getPatch(self, res):
        d = self.dovc(["diff"])
        d.addCallback(self.readPatch, self.patchlevel)
        return d

class TlaExtractor(SourceStampExtractor):
    patchlevel = 1
    vcexe = "tla"
    def getBaseRevision(self):
        # 'tla logs --full' gives us ARCHIVE/BRANCH--REVISION
        # 'tla logs' gives us REVISION
        d = self.dovc(["logs", "--full", "--reverse"])
        d.addCallback(self.parseStatus)
        return d
    def parseStatus(self, res):
        tid = res.split("\n")[0].strip()
        slash = tid.index("/")
        dd = tid.rindex("--")
        self.branch = tid[slash+1:dd]
        self.baserev = tid[dd+2:]

    def getPatch(self, res):
        d = self.dovc(["changes", "--diffs"])
        d.addCallback(self.readPatch, self.patchlevel)
        return d

class BzrExtractor(SourceStampExtractor):
    patchlevel = 0
    vcexe = "bzr"
    def getBaseRevision(self):
        d = self.dovc(["revision-info","-rsubmit:"])
        d.addCallback(self.get_revision_number)
        return d

    def get_revision_number(self, out):
        revno, revid= out.split()
        self.baserev = 'revid:' + revid
        return

    def getPatch(self, res):
        d = self.dovc(["diff","-r%s.." % self.baserev])
        d.addCallback(self.readPatch, self.patchlevel)
        return d

class MercurialExtractor(SourceStampExtractor):
    patchlevel = 1
    vcexe = "hg"
    def getBaseRevision(self):
        d = self.dovc(["identify"])
        d.addCallback(self.parseStatus)
        return d
    def parseStatus(self, output):
        m = re.search(r'^(\w+)', output)
        self.baserev = m.group(0)
    def getPatch(self, res):
        d = self.dovc(["diff"])
        d.addCallback(self.readPatch, self.patchlevel)
        return d

class DarcsExtractor(SourceStampExtractor):
    patchlevel = 1
    vcexe = "darcs"
    def getBaseRevision(self):
        d = self.dovc(["changes", "--context"])
        d.addCallback(self.parseStatus)
        return d
    def parseStatus(self, res):
        self.baserev = res # the whole context file
    def getPatch(self, res):
        d = self.dovc(["diff", "-u"])
        d.addCallback(self.readPatch, self.patchlevel)
        return d

class GitExtractor(SourceStampExtractor):
    patchlevel = 1
    vcexe = "git"

    def getBaseRevision(self):
        d = self.dovc(["branch", "--no-color", "-v", "--no-abbrev"])
        d.addCallback(self.parseStatus)
        return d

    def readConfig(self):
        d = self.dovc(["config", "-l"])
        d.addCallback(self.parseConfig)
        return d

    def parseConfig(self, res):
        git_config = {}
        for l in res.split("\n"):
            if l.strip():
                parts = l.strip().split("=", 2)
                git_config[parts[0]] = parts[1]

        # If we're tracking a remote, consider that the base.
        remote = git_config.get("branch." + self.branch + ".remote")
        ref = git_config.get("branch." + self.branch + ".merge")
        if remote and ref:
            remote_branch = ref.split("/", 3)[-1]
            d = self.dovc(["rev-parse", remote + "/" + remote_branch])
            d.addCallback(self.override_baserev)
            return d

    def override_baserev(self, res):
        self.baserev = res.strip()

    def parseStatus(self, res):
        # The current branch is marked by '*' at the start of the
        # line, followed by the branch name and the SHA1.
        #
        # Branch names may contain pretty much anything but whitespace.
        m = re.search(r'^\* (\S+)\s+([0-9a-f]{40})', res, re.MULTILINE)
        if m:
            self.baserev = m.group(2)
            # If a branch is specified, parse out the rev it points to
            # and extract the local name (assuming it has a slash).
            # This may break if someone specifies the name of a local
            # branch that has a slash in it and has no corresponding
            # remote branch (or something similarly contrived).
            if self.branch:
                d = self.dovc(["rev-parse", self.branch])
                if '/' in self.branch:
                    self.branch = self.branch.split('/', 1)[1]
                d.addCallback(self.override_baserev)
                return d
            else:
                self.branch = m.group(1)
                return self.readConfig()
        raise IndexError("Could not find current GIT branch: %s" % res)

    def getPatch(self, res):
        d = self.dovc(["diff", self.baserev])
        d.addCallback(self.readPatch, self.patchlevel)
        return d

def getSourceStamp(vctype, treetop, branch=None):
    if vctype == "cvs":
        e = CVSExtractor(treetop, branch)
    elif vctype == "svn":
        e = SVNExtractor(treetop, branch)
    elif vctype == "baz":
        e = BazExtractor(treetop, branch)
    elif vctype == "bzr":
        e = BzrExtractor(treetop, branch)
    elif vctype == "tla":
        e = TlaExtractor(treetop, branch)
    elif vctype == "hg":
        e = MercurialExtractor(treetop, branch)
    elif vctype == "darcs":
        e = DarcsExtractor(treetop, branch)
    elif vctype == "git":
        e = GitExtractor(treetop, branch)
    else:
        raise KeyError("unknown vctype '%s'" % vctype)
    return e.get()


def ns(s):
    return "%d:%s," % (len(s), s)

def createJobfile(bsid, branch, baserev, patchlevel, diff, builderNames):
    job = ""
    job += ns("1")
    job += ns(bsid)
    job += ns(branch)
    job += ns(str(baserev))
    job += ns("%d" % patchlevel)
    job += ns(diff)
    for bn in builderNames:
        job += ns(bn)
    return job

def getTopdir(topfile, start=None):
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
            break # we've hit the root
        here = next
        toomany -= 1
    raise ValueError("Unable to find topfile '%s' anywhere from %s upwards"
                     % (topfile, start))

class RemoteTryPP(protocol.ProcessProtocol):
    def __init__(self, job):
        self.job = job
        self.d = defer.Deferred()
    def connectionMade(self):
        self.transport.write(self.job)
        self.transport.closeStdin()
    def outReceived(self, data):
        sys.stdout.write(data)
    def errReceived(self, data):
        sys.stderr.write(data)
    def processEnded(self, status_object):
        sig = status_object.value.signal
        rc = status_object.value.exitCode
        if sig != None or rc != 0:
            self.d.errback(RuntimeError("remote 'buildbot tryserver' failed"
                                        ": sig=%s, rc=%s" % (sig, rc)))
            return
        self.d.callback((sig, rc))

class BuildSetStatusGrabber:
    retryCount = 5 # how many times to we try to grab the BuildSetStatus?
    retryDelay = 3 # seconds to wait between attempts

    def __init__(self, status, bsid):
        self.status = status
        self.bsid = bsid

    def grab(self):
        # return a Deferred that either fires with the BuildSetStatus
        # reference or errbacks because we were unable to grab it
        self.d = defer.Deferred()
        # wait a second before querying to give the master's maildir watcher
        # a chance to see the job
        reactor.callLater(1, self.go)
        return self.d

    def go(self, dummy=None):
        if self.retryCount == 0:
            raise RuntimeError("couldn't find matching buildset")
        self.retryCount -= 1
        d = self.status.callRemote("getBuildSets")
        d.addCallback(self._gotSets)

    def _gotSets(self, buildsets):
        for bs,bsid in buildsets:
            if bsid == self.bsid:
                # got it
                self.d.callback(bs)
                return
        d = defer.Deferred()
        d.addCallback(self.go)
        reactor.callLater(self.retryDelay, d.callback, None)


class Try(pb.Referenceable):
    buildsetStatus = None
    quiet = False

    def __init__(self, config):
        self.config = config
        self.connect = self.getopt('connect')
        assert self.connect, "you must specify a connect style: ssh or pb"
        self.builderNames = self.getopt('builders')

    def getopt(self, config_name, default=None):
        value = self.config.get(config_name)
        if value is None or value == []:
            value = default
        return value

    def createJob(self):
        # returns a Deferred which fires when the job parameters have been
        # created

        # generate a random (unique) string. It would make sense to add a
        # hostname and process ID here, but a) I suspect that would cause
        # windows portability problems, and b) really this is good enough
        self.bsid = "%d-%s" % (time.time(), random.randint(0, 1000000))

        # common options
        branch = self.getopt("branch")

        difffile = self.config.get("diff")
        if difffile:
            baserev = self.config.get("baserev")
            if difffile == "-":
                diff = sys.stdin.read()
            else:
                diff = open(difffile,"r").read()
            patch = (self.config['patchlevel'], diff)
            ss = SourceStamp(branch, baserev, patch)
            d = defer.succeed(ss)
        else:
            vc = self.getopt("vc")
            if vc in ("cvs", "svn"):
                # we need to find the tree-top
                topdir = self.getopt("try-topdir")
                if topdir:
                    treedir = os.path.expanduser(topdir)
                else:
                    topfile = self.getopt("try-topfile")
                    treedir = getTopdir(topfile)
            else:
                treedir = os.getcwd()
            d = getSourceStamp(vc, treedir, branch)
        d.addCallback(self._createJob_1)
        return d

    def _createJob_1(self, ss):
        self.sourcestamp = ss
        if self.connect == "ssh":
            patchlevel, diff = ss.patch
            revspec = ss.revision
            if revspec is None:
                revspec = ""
            self.jobfile = createJobfile(self.bsid,
                                         ss.branch or "", revspec,
                                         patchlevel, diff,
                                         self.builderNames)

    def fakeDeliverJob(self):
        # Display the job to be delivered, but don't perform delivery.
        ss = self.sourcestamp
        print ("Job:\n\tBranch: %s\n\tRevision: %s\n\tBuilders: %s\n%s"
               % (ss.branch,
                  ss.revision,
                  self.builderNames,
                  ss.patch[1]))
        d = defer.Deferred()
        d.callback(True)
        return d

    def deliverJob(self):
        # returns a Deferred that fires when the job has been delivered

        if self.connect == "ssh":
            tryhost = self.getopt("tryhost")
            tryuser = self.getopt("username")
            trydir = self.getopt("trydir")

            argv = ["ssh", "-l", tryuser, tryhost,
                    "buildbot", "tryserver", "--jobdir", trydir]
            # now run this command and feed the contents of 'job' into stdin

            pp = RemoteTryPP(self.jobfile)
            p = reactor.spawnProcess(pp, argv[0], argv, os.environ)
            d = pp.d
            return d
        if self.connect == "pb":
            user = self.getopt("username")
            passwd = self.getopt("passwd")
            master = self.getopt("master")
            tryhost, tryport = master.split(":")
            tryport = int(tryport)
            f = pb.PBClientFactory()
            d = f.login(credentials.UsernamePassword(user, passwd))
            reactor.connectTCP(tryhost, tryport, f)
            d.addCallback(self._deliverJob_pb)
            return d
        raise RuntimeError("unknown connecttype '%s', should be 'ssh' or 'pb'"
                           % self.connect)

    def _deliverJob_pb(self, remote):
        ss = self.sourcestamp

        d = remote.callRemote("try",
                              ss.branch,
                              ss.revision,
                              ss.patch,
                              self.builderNames,
                              self.config.get('properties', {}))
        d.addCallback(self._deliverJob_pb2)
        return d
    def _deliverJob_pb2(self, status):
        self.buildsetStatus = status
        return status

    def getStatus(self):
        # returns a Deferred that fires when the builds have finished, and
        # may emit status messages while we wait
        wait = bool(self.getopt("wait", "try_wait", False))
        if not wait:
            # TODO: emit the URL where they can follow the builds. This
            # requires contacting the Status server over PB and doing
            # getURLForThing() on the BuildSetStatus. To get URLs for
            # individual builds would require we wait for the builds to
            # start.
            print "not waiting for builds to finish"
            return
        d = self.running = defer.Deferred()
        if self.buildsetStatus:
            self._getStatus_1()
        # contact the status port
        # we're probably using the ssh style
        master = self.getopt("master")
        host, port = master.split(":")
        port = int(port)
        self.announce("contacting the status port at %s:%d" % (host, port))
        f = pb.PBClientFactory()
        creds = credentials.UsernamePassword("statusClient", "clientpw")
        d = f.login(creds)
        reactor.connectTCP(host, port, f)
        d.addCallback(self._getStatus_ssh_1)
        return self.running

    def _getStatus_ssh_1(self, remote):
        # find a remotereference to the corresponding BuildSetStatus object
        self.announce("waiting for job to be accepted")
        g = BuildSetStatusGrabber(remote, self.bsid)
        d = g.grab()
        d.addCallback(self._getStatus_1)
        return d

    def _getStatus_1(self, res=None):
        if res:
            self.buildsetStatus = res
        # gather the set of BuildRequests
        d = self.buildsetStatus.callRemote("getBuildRequests")
        d.addCallback(self._getStatus_2)

    def _getStatus_2(self, brs):
        self.builderNames = []
        self.buildRequests = {}

        # self.builds holds the current BuildStatus object for each one
        self.builds = {}

        # self.outstanding holds the list of builderNames which haven't
        # finished yet
        self.outstanding = []

        # self.results holds the list of build results. It holds a tuple of
        # (result, text)
        self.results = {}

        # self.currentStep holds the name of the Step that each build is
        # currently running
        self.currentStep = {}

        # self.ETA holds the expected finishing time (absolute time since
        # epoch)
        self.ETA = {}

        for n,br in brs:
            self.builderNames.append(n)
            self.buildRequests[n] = br
            self.builds[n] = None
            self.outstanding.append(n)
            self.results[n] = [None,None]
            self.currentStep[n] = None
            self.ETA[n] = None
            # get new Builds for this buildrequest. We follow each one until
            # it finishes or is interrupted.
            br.callRemote("subscribe", self)

        # now that those queries are in transit, we can start the
        # display-status-every-30-seconds loop
        self.printloop = task.LoopingCall(self.printStatus)
        self.printloop.start(3, now=False)


    # these methods are invoked by the status objects we've subscribed to

    def remote_newbuild(self, bs, builderName):
        if self.builds[builderName]:
            self.builds[builderName].callRemote("unsubscribe", self)
        self.builds[builderName] = bs
        bs.callRemote("subscribe", self, 20)
        d = bs.callRemote("waitUntilFinished")
        d.addCallback(self._build_finished, builderName)

    def remote_stepStarted(self, buildername, build, stepname, step):
        self.currentStep[buildername] = stepname

    def remote_stepFinished(self, buildername, build, stepname, step, results):
        pass

    def remote_buildETAUpdate(self, buildername, build, eta):
        self.ETA[buildername] = now() + eta

    def _build_finished(self, bs, builderName):
        # we need to collect status from the newly-finished build. We don't
        # remove the build from self.outstanding until we've collected
        # everything we want.
        self.builds[builderName] = None
        self.ETA[builderName] = None
        self.currentStep[builderName] = "finished"
        d = bs.callRemote("getResults")
        d.addCallback(self._build_finished_2, bs, builderName)
        return d
    def _build_finished_2(self, results, bs, builderName):
        self.results[builderName][0] = results
        d = bs.callRemote("getText")
        d.addCallback(self._build_finished_3, builderName)
        return d
    def _build_finished_3(self, text, builderName):
        self.results[builderName][1] = text
        
        self.outstanding.remove(builderName)
        if not self.outstanding:
            # all done
            return self.statusDone()

    def printStatus(self):
        names = self.buildRequests.keys()
        names.sort()
        for n in names:
            if n not in self.outstanding:
                # the build is finished, and we have results
                code,text = self.results[n]
                t = builder.Results[code]
                if text:
                    t += " (%s)" % " ".join(text)
            elif self.builds[n]:
                t = self.currentStep[n] or "building"
                if self.ETA[n]:
                    t += " [ETA %ds]" % (self.ETA[n] - now())
            else:
                t = "no build"
            self.announce("%s: %s" % (n, t))
        self.announce("")

    def statusDone(self):
        self.printloop.stop()
        print "All Builds Complete"
        # TODO: include a URL for all failing builds
        names = self.buildRequests.keys()
        names.sort()
        happy = True
        for n in names:
            code,text = self.results[n]
            t = "%s: %s" % (n, builder.Results[code])
            if text:
                t += " (%s)" % " ".join(text)
            print t
            if self.results[n] != builder.SUCCESS:
                happy = False

        if happy:
            self.exitcode = 0
        else:
            self.exitcode = 1
        self.running.callback(self.exitcode)

    def announce(self, message):
        if not self.quiet:
            print message

    def run(self):
        # we can't do spawnProcess until we're inside reactor.run(), so get
        # funky
        print "using '%s' connect method" % self.connect
        self.exitcode = 0
        d = defer.Deferred()
        d.addCallback(lambda res: self.createJob())
        d.addCallback(lambda res: self.announce("job created"))
        deliver = self.deliverJob
        if bool(self.config.get("dryrun")):
            deliver = self.fakeDeliverJob
        d.addCallback(lambda res: deliver())
        d.addCallback(lambda res: self.announce("job has been delivered"))
        d.addCallback(lambda res: self.getStatus())
        d.addErrback(log.err)
        d.addCallback(self.cleanup)
        d.addCallback(lambda res: reactor.stop())

        reactor.callLater(0, d.callback, None)
        reactor.run()
        sys.exit(self.exitcode)

    def logErr(self, why):
        log.err(why)
        print "error during 'try' processing"
        print why

    def cleanup(self, res=None):
        if self.buildsetStatus:
            self.buildsetStatus.broker.transport.loseConnection()


    
