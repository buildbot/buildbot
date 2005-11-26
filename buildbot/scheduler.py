# -*- test-case-name: buildbot.test.test_dependencies -*-

import time, os.path

from twisted.internet import reactor
from twisted.application import service, internet
from twisted.python import log
from twisted.protocols import basic
from twisted.cred import portal, checkers
from twisted.spread import pb

from buildbot import interfaces, buildset, util, pbutil
from buildbot.util import now
from buildbot.status import builder
from buildbot.twcompat import implements, providedBy
from buildbot.sourcestamp import SourceStamp
from buildbot.changes import maildirtwisted


class BaseScheduler(service.MultiService, util.ComparableMixin):
    if implements:
        implements(interfaces.IScheduler)
    else:
        __implements__ = interfaces.IScheduler,

    def __init__(self, name):
        service.MultiService.__init__(self)
        self.name = name

    def __repr__(self):
        return "<Scheduler '%s'>" % self.name

    def submit(self, bs):
        self.parent.submitBuildSet(bs)

class BaseUpstreamScheduler(BaseScheduler):
    if implements:
        implements(interfaces.IUpstreamScheduler)
    else:
        __implements__ = interfaces.IUpstreamScheduler,

    def __init__(self, name):
        BaseScheduler.__init__(self, name)
        self.successWatchers = []

    def subscribeToSuccessfulBuilds(self, watcher):
        self.successWatchers.append(watcher)
    def unsubscribeToSuccessfulBuilds(self, watcher):
        self.successWatchers.remove(watcher)

    def submit(self, bs):
        d = bs.waitUntilFinished()
        d.addCallback(self.buildSetFinished)
        self.parent.submitBuildSet(bs)

    def buildSetFinished(self, bss):
        if not self.running:
            return
        if bss.getResults() == builder.SUCCESS:
            ss = bss.getSourceStamp()
            for w in self.successWatchers:
                w(ss)


class Scheduler(BaseUpstreamScheduler):
    """The default Scheduler class will run a build after some period of time
    called the C{treeStableTimer}, on a given set of Builders. It only pays
    attention to a single branch. You you can provide a C{fileIsImportant}
    function which will evaluate each Change to decide whether or not it
    should trigger a new build.
    """

    fileIsImportant = None
    compare_attrs = ('name', 'treeStableTimer', 'builderNames', 'branch',
                     'fileIsImportant')
    
    def __init__(self, name, branch, treeStableTimer, builderNames,
                 fileIsImportant=None):
        """
        @param name: the name of this Scheduler
        @param branch: The branch name that the Scheduler should pay
                       attention to. Any Change that is not on this branch
                       will be ignored. It can be set to None to only pay
                       attention to the default branch.
        @param treeStableTimer: the duration, in seconds, for which the tree
                                must remain unchanged before a build will be
                                triggered. This is intended to avoid builds
                                of partially-committed fixes.
        @param builderNames: a list of Builder names. When this Scheduler
                             decides to start a set of builds, they will be
                             run on the Builders named by this list.

        @param fileIsImportant: A callable which takes one argument (a Change
                                instance) and returns True if the change is
                                worth building, and False if it is not.
                                Unimportant Changes are accumulated until the
                                build is triggered by an important change.
                                The default value of None means that all
                                Changes are important.
        """

        BaseUpstreamScheduler.__init__(self, name)
        self.treeStableTimer = treeStableTimer
        for b in builderNames:
            assert type(b) is str
        self.builderNames = builderNames
        self.branch = branch
        if fileIsImportant:
            assert callable(fileIsImportant)
            self.fileIsImportant = fileIsImportant

        self.importantChanges = []
        self.unimportantChanges = []
        self.nextBuildTime = None
        self.timer = None

    def listBuilderNames(self):
        return self.builderNames

    def getPendingBuildTimes(self):
        if self.nextBuildTime is not None:
            return [self.nextBuildTime]
        return []

    def addChange(self, change):
        if change.branch != self.branch:
            log.msg("%s ignoring off-branch %s" % (self, change))
            return
        if not self.fileIsImportant:
            self.addImportantChange(change)
        elif self.fileIsImportant(change):
            self.addImportantChange(change)
        else:
            self.addUnimportantChange(change)

    def addImportantChange(self, change):
        log.msg("%s: change is important, adding %s" % (self, change))
        self.importantChanges.append(change)
        self.nextBuildTime = max(self.nextBuildTime,
                                 change.when + self.treeStableTimer)
        self.setTimer(self.nextBuildTime)

    def addUnimportantChange(self, change):
        log.msg("%s: change is not important, adding %s" % (self, change))
        self.unimportantChanges.append(change)

    def setTimer(self, when):
        log.msg("%s: setting timer to %s" %
                (self, time.strftime("%H:%M:%S", time.localtime(when))))
        now = util.now()
        if when < now:
            when = now + 1
        if self.timer:
            self.timer.cancel()
        self.timer = reactor.callLater(when - now, self.fireTimer)

    def stopTimer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def fireTimer(self):
        # clear out our state
        self.timer = None
        self.nextBuildTime = None
        changes = self.importantChanges + self.unimportantChanges
        self.importantChanges = []
        self.unimportantChanges = []

        # create a BuildSet, submit it to the BuildMaster
        bs = buildset.BuildSet(self.builderNames,
                               SourceStamp(changes=changes))
        self.submit(bs)

    def stopService(self):
        self.stopTimer()
        return service.MultiService.stopService(self)


class AnyBranchScheduler(BaseUpstreamScheduler):
    """This Scheduler will handle changes on a variety of branches. It will
    accumulate Changes for each branch separately. It works by creating a
    separate Scheduler for each new branch it sees."""

    schedulerFactory = Scheduler
    fileIsImportant = None

    compare_attrs = ('name', 'branches', 'treeStableTimer', 'builderNames',
                     'fileIsImportant')

    def __init__(self, name, branches, treeStableTimer, builderNames,
                 fileIsImportant=None):
        """
        @param name: the name of this Scheduler
        @param branches: The branch names that the Scheduler should pay
                         attention to. Any Change that is not on one of these
                         branches will be ignored. It can be set to None to
                         accept changes from any branch. Don't use [] (an
                         empty list), because that means we don't pay
                         attention to *any* branches, so we'll never build
                         anything.
        @param treeStableTimer: the duration, in seconds, for which the tree
                                must remain unchanged before a build will be
                                triggered. This is intended to avoid builds
                                of partially-committed fixes.
        @param builderNames: a list of Builder names. When this Scheduler
                             decides to start a set of builds, they will be
                             run on the Builders named by this list.

        @param fileIsImportant: A callable which takes one argument (a Change
                                instance) and returns True if the change is
                                worth building, and False if it is not.
                                Unimportant Changes are accumulated until the
                                build is triggered by an important change.
                                The default value of None means that all
                                Changes are important.
        """

        BaseUpstreamScheduler.__init__(self, name)
        self.treeStableTimer = treeStableTimer
        for b in builderNames:
            assert type(b) is str
        self.builderNames = builderNames
        self.branches = branches
        if self.branches == []:
            log.msg("AnyBranchScheduler %s: branches=[], so we will ignore "
                    "all branches, and never trigger any builds. Please set "
                    "branches=None to mean 'all branches'" % self)
            # consider raising an exception here, to make this warning more
            # prominent, but I can vaguely imagine situations where you might
            # want to comment out branches temporarily and wouldn't
            # appreciate it being treated as an error.
        if fileIsImportant:
            assert callable(fileIsImportant)
            self.fileIsImportant = fileIsImportant
        self.schedulers = {} # one per branch

    def __repr__(self):
        return "<AnyBranchScheduler '%s'>" % self.name

    def listBuilderNames(self):
        return self.builderNames

    def getPendingBuildTimes(self):
        bts = []
        for s in self.schedulers.values():
            if s.nextBuildTime is not None:
                bts.append(s.nextBuildTime)
        return bts

    def addChange(self, change):
        branch = change.branch
        if self.branches is not None and branch not in self.branches:
            log.msg("%s ignoring off-branch %s" % (self, change))
            return
        s = self.schedulers.get(branch)
        if not s:
            name = self.name + "." + branch
            s = self.schedulerFactory(name, branch,
                                      self.treeStableTimer,
                                      self.builderNames,
                                      self.fileIsImportant)
            s.successWatchers = self.successWatchers
            s.setServiceParent(self)
            # TODO: does this result in schedulers that stack up forever?
            # When I make the persistify-pass, think about this some more.
            self.schedulers[branch] = s
        s.addChange(change)

    def submitBuildSet(self, bs):
        self.parent.submitBuildSet(bs)


class Dependent(BaseUpstreamScheduler):
    """This scheduler runs some set of 'downstream' builds when the
    'upstream' scheduler has completed successfully."""

    compare_attrs = ('name', 'upstream', 'builders')

    def __init__(self, name, upstream, builderNames):
        assert providedBy(upstream, interfaces.IUpstreamScheduler)
        BaseUpstreamScheduler.__init__(self, name)
        self.upstream = upstream
        self.builderNames = builderNames

    def listBuilderNames(self):
        return self.builderNames

    def getPendingBuildTimes(self):
        # report the upstream's value
        return self.upstream.getPendingBuildTimes()

    def startService(self):
        service.MultiService.startService(self)
        self.upstream.subscribeToSuccessfulBuilds(self.upstreamBuilt)

    def stopService(self):
        d = service.MultiService.stopService(self)
        self.upstream.unsubscribeToSuccessfulBuilds(self.upstreamBuilt)
        return d

    def upstreamBuilt(self, ss):
        bs = buildset.BuildSet(self.builderNames, ss)
        self.submit(bs)



class Periodic(BaseUpstreamScheduler):
    """Instead of watching for Changes, this Scheduler can just start a build
    at fixed intervals. The C{periodicBuildTimer} parameter sets the number
    of seconds to wait between such periodic builds. The first build will be
    run immediately."""

    # TODO: consider having this watch another (changed-based) scheduler and
    # merely enforce a minimum time between builds.

    compare_attrs = ('name', 'builderNames', 'periodicBuildTimer', 'branch')

    def __init__(self, name, builderNames, periodicBuildTimer,
                 branch=None):
        BaseUpstreamScheduler.__init__(self, name)
        self.builderNames = builderNames
        self.periodicBuildTimer = periodicBuildTimer
        self.branch = branch
        self.timer = internet.TimerService(self.periodicBuildTimer,
                                           self.doPeriodicBuild)
        self.timer.setServiceParent(self)

    def listBuilderNames(self):
        return self.builderNames

    def getPendingBuildTimes(self):
        # TODO: figure out when self.timer is going to fire next and report
        # that
        return []

    def doPeriodicBuild(self):
        bs = buildset.BuildSet(self.builderNames,
                               SourceStamp(branch=self.branch))
        self.submit(bs)

class TryBase(service.MultiService, util.ComparableMixin):
    if implements:
        implements(interfaces.IScheduler)
    else:
        __implements__ = (interfaces.IScheduler,
                          service.MultiService.__implements__)

    def __init__(self, name, builderNames):
        service.MultiService.__init__(self)
        self.name = name
        self.builderNames = builderNames

    def listBuilderNames(self):
        return self.builderNames

    def getPendingBuildTimes(self):
        # we can't predict what the developers are going to do in the future
        return []

    def addChange(self, change):
        # Try schedulers ignore Changes
        pass


class BadJobfile(Exception):
    pass

class JobFileScanner(basic.NetstringReceiver):
    def __init__(self):
        self.strings = []
        self.transport = self # so transport.loseConnection works
        self.error = False

    def stringReceived(self, s):
        self.strings.append(s)

    def loseConnection(self):
        self.error = True

class Try_Jobdir(TryBase):
    compare_attrs = ["name", "builderNames", "jobdir"]

    def __init__(self, name, builderNames, jobdir):
        TryBase.__init__(self, name, builderNames)
        self.jobdir = jobdir
        self.watcher = maildirtwisted.MaildirService()
        self.watcher.setServiceParent(self)

    def setServiceParent(self, parent):
        self.watcher.setBasedir(os.path.join(parent.basedir, self.jobdir))
        TryBase.setServiceParent(self, parent)

    def parseJob(self, f):
        # jobfiles are serialized build requests. Each is a list of
        # serialized netstrings, in the following order:
        #  "1", the version number of this format
        #  buildsetID, arbitrary string, used to find the buildSet later
        #  branch name, "" for default-branch
        #  base revision
        #  patchlevel, usually "1"
        #  patch
        #  builderNames...
        p = JobFileScanner()
        p.dataReceived(f.read())
        if p.error:
            raise BadJobfile("unable to parse netstrings")
        s = p.strings
        ver = s.pop(0)
        if ver != "1":
            raise BadJobfile("unknown version '%s'" % ver)
        buildsetID, branch, baserev, patchlevel, diff = s[:5]
        builderNames = s[5:]
        if branch == "":
            branch = None
        patchlevel = int(patchlevel)
        patch = (patchlevel, diff)
        ss = SourceStamp(branch, baserev, patch)
        return builderNames, ss, buildsetID

    def messageReceived(self, filename):
        md = os.path.join(self.parent.basedir, self.jobdir)
        path = os.path.join(md, "new", filename)
        f = open(path, "r")
        os.rename(os.path.join(md, "new", filename),
                  os.path.join(md, "cur", filename))
        try:
            builderNames, ss, bsid = self.parseJob(f)
        except BadJobfile:
            log.msg("%s reports a bad jobfile in %s" % (self, filename))
            log.err()
            return
        # compare builderNames against self.builderNames
        # TODO: think about this some more.. why bother restricting it?
        # perhaps self.builderNames should be used as the default list
        # instead of being used as a restriction?
        for b in builderNames:
            if not b in self.builderNames:
                log.msg("%s got jobfile %s with builder %s" % (self,
                                                               filename, b))
                log.msg(" but that wasn't in our list: %s"
                        % (self.builderNames,))
                return

        reason = "'try' job"
        bs = buildset.BuildSet(builderNames, ss, reason=reason, bsid=bsid)
        self.parent.submitBuildSet(bs)

class Try_Userpass(TryBase):
    compare_attrs = ["name", "builderNames", "port", "userpass"]

    if implements:
        implements(portal.IRealm)
    else:
        __implements__ = (portal.IRealm,
                          TryBase.__implements__)

    def __init__(self, name, builderNames, port, userpass):
        TryBase.__init__(self, name, builderNames)
        self.port = port
        self.userpass = userpass
        c = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        for user,passwd in self.userpass:
            c.addUser(user, passwd)

        p = portal.Portal(self)
        p.registerChecker(c)
        f = pb.PBServerFactory(p)
        s = internet.TCPServer(port, f)
        s.setServiceParent(self)

    def getPort(self):
        # utility method for tests: figure out which TCP port we just opened.
        return self.services[0]._port.getHost().port

    def requestAvatar(self, avatarID, mind, interface):
        log.msg("%s got connection from user %s" % (self, avatarID))
        assert interface == pb.IPerspective
        p = Try_Userpass_Perspective(self, avatarID)
        return (pb.IPerspective, p, lambda: None)

    def submitBuildSet(self, bs):
        return self.parent.submitBuildSet(bs)

class Try_Userpass_Perspective(pbutil.NewCredPerspective):
    def __init__(self, parent, username):
        self.parent = parent
        self.username = username

    def perspective_try(self, branch, revision, patch, builderNames):
        log.msg("user %s requesting build on builders %s" % (self.username,
                                                             builderNames))
        for b in builderNames:
            if not b in self.parent.builderNames:
                log.msg("%s got job with builder %s" % (self, b))
                log.msg(" but that wasn't in our list: %s"
                        % (self.parent.builderNames,))
                return
        ss = SourceStamp(branch, revision, patch)
        reason = "'try' job from user %s" % self.username
        bs = buildset.BuildSet(builderNames, ss, reason=reason)
        self.parent.submitBuildSet(bs)

        # return a remotely-usable BuildSetStatus object
        from buildbot.status.client import makeRemote
        return makeRemote(bs.status)

