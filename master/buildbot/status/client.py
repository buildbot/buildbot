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


from twisted.application import strports
from twisted.cred import checkers
from twisted.cred import portal
from twisted.python import components
from twisted.python import log as twlog
from twisted.spread import pb

from buildbot import interfaces
from buildbot.changes import changes
from buildbot.status import base
from buildbot.status import logfile
from buildbot.util.eventual import eventually
from zope.interface import Interface
from zope.interface import implements


class IRemote(Interface):
    pass


def makeRemote(obj):
    # we want IRemote(None) to be None, but you can't really do that with
    # adapters, so we fake it
    if obj is None:
        return None
    return IRemote(obj)


class RemoteBuildSet(pb.Referenceable):

    def __init__(self, buildset):
        self.b = buildset

    def remote_getSourceStamp(self):
        return self.b.getSourceStamp()

    def remote_getReason(self):
        return self.b.getReason()

    def remote_getID(self):
        return self.b.getID()

    def remote_getBuilderNames(self):
        return self.b.getBuilderNames()  # note: passes along the Deferred

    def remote_getBuildRequests(self):
        """Returns a list of (builderName, BuildRequest) tuples."""
        d = self.b.getBuilderNamesAndBuildRequests()

        def add_remote(buildrequests):
            for k, v in buildrequests.iteritems():
                buildrequests[k] = IRemote(v)
            return buildrequests.items()
        d.addCallback(add_remote)
        return d

    def remote_isFinished(self):
        return self.b.isFinished()

    def remote_waitUntilFinished(self):
        d = self.b.waitUntilFinished()
        d.addCallback(makeRemote)
        return d

    def remote_getResults(self):
        return self.b.getResults()

components.registerAdapter(RemoteBuildSet,
                           interfaces.IBuildSetStatus, IRemote)


class RemoteBuilder(pb.Referenceable):

    def __init__(self, builder):
        self.b = builder

    def remote_getName(self):
        return self.b.getName()

    def remote_getCategory(self):
        return self.b.getCategory()

    def remote_getState(self):
        state, builds = self.b.getState()
        return (state,
                None,  # TODO: remove leftover ETA
                [makeRemote(b) for b in builds])

    def remote_getSlaves(self):
        return [IRemote(s) for s in self.b.getSlaves()]

    def remote_getLastFinishedBuild(self):
        return makeRemote(self.b.getLastFinishedBuild())

    def remote_getCurrentBuilds(self):
        return [IRemote(b) for b in self.b.getCurrentBuilds()]

    def remote_getBuild(self, number):
        return makeRemote(self.b.getBuild(number))

    def remote_getEvent(self, number):
        return IRemote(self.b.getEvent(number))

components.registerAdapter(RemoteBuilder,
                           interfaces.IBuilderStatus, IRemote)


class RemoteBuildRequest(pb.Referenceable):

    def __init__(self, buildreq):
        self.b = buildreq
        # mapping of observers (RemoteReference instances) to local callable
        # objects that have been passed to BuildRequestStatus.subscribe
        self.observers = []

    def remote_getSourceStamp(self):
        # note that this now returns a Deferred
        return self.b.getSourceStamp()

    def remote_getBuilderName(self):
        return self.b.getBuilderName()

    def remote_subscribe(self, observer):
        """The observer's remote_newbuild method will be called (with two
        arguments: the RemoteBuild object, and our builderName) for each new
        Build that is created to handle this BuildRequest."""
        def send(bs):
            d = observer.callRemote("newbuild",
                                    IRemote(bs), self.b.getBuilderName())
            d.addErrback(twlog.err,
                         "while calling client-side remote_newbuild")
        self.observers.append((observer, send))
        self.b.subscribe(send)

    def remote_unsubscribe(self, observer):
        for i, (obs, send) in enumerate(self.observers):
            if obs == observer:
                del self.observers[i]
                self.b.unsubscribe(send)
                break

components.registerAdapter(RemoteBuildRequest,
                           interfaces.IBuildRequestStatus, IRemote)


class RemoteBuild(pb.Referenceable):

    def __init__(self, build):
        self.b = build
        self.observers = []

    def remote_getBuilderName(self):
        return self.b.getBuilder().getName()

    def remote_getNumber(self):
        return self.b.getNumber()

    def remote_getReason(self):
        return self.b.getReason()

    def remote_getChanges(self):
        return [IRemote(c) for c in self.b.getChanges()]

    def remote_getRevisions(self):
        return self.b.getRevisions()

    def remote_getResponsibleUsers(self):
        return self.b.getResponsibleUsers()

    def remote_getSteps(self):
        return [IRemote(s) for s in self.b.getSteps()]

    def remote_getTimes(self):
        return self.b.getTimes()

    def remote_isFinished(self):
        return self.b.isFinished()

    def remote_waitUntilFinished(self):
        # the Deferred returned by callRemote() will fire when this build is
        # finished
        d = self.b.waitUntilFinished()
        d.addCallback(lambda res: self)
        return d

    def remote_getETA(self):
        return self.b.getETA()

    def remote_getCurrentStep(self):
        return makeRemote(self.b.getCurrentStep())

    def remote_getText(self):
        return self.b.getText()

    def remote_getResults(self):
        return self.b.getResults()

    def remote_getLogs(self):
        logs = {}
        for name, log in self.b.getLogs().items():
            logs[name] = IRemote(log)
        return logs

    def remote_getProperties(self):
        return self.b.getProperties().asDict()

    def remote_subscribe(self, observer, updateInterval=None):
        """The observer will have remote_stepStarted(buildername, build,
        stepname, step), remote_stepFinished(buildername, build, stepname,
        step, results), and maybe remote_buildETAUpdate(buildername, build,
        eta)) messages sent to it."""
        self.observers.append(observer)
        s = BuildSubscriber(observer)
        self.b.subscribe(s, updateInterval)
        observer.notifyOnDisconnect(lambda _: self.b.unsubscribe(s))

    def remote_unsubscribe(self, observer):
        # TODO: is the observer automatically unsubscribed when the build
        # finishes? Or are they responsible for unsubscribing themselves
        # anyway? How do we avoid a race condition here?
        for o in self.observers:
            if o == observer:
                self.observers.remove(o)


components.registerAdapter(RemoteBuild,
                           interfaces.IBuildStatus, IRemote)


class BuildSubscriber:

    def __init__(self, observer):
        self.observer = observer

    def buildETAUpdate(self, build, eta):
        self.observer.callRemote("buildETAUpdate",
                                 build.getBuilder().getName(),
                                 IRemote(build),
                                 eta)

    def stepStarted(self, build, step):
        self.observer.callRemote("stepStarted",
                                 build.getBuilder().getName(),
                                 IRemote(build),
                                 step.getName(), IRemote(step))
        return None

    def stepFinished(self, build, step, results):
        self.observer.callRemote("stepFinished",
                                 build.getBuilder().getName(),
                                 IRemote(build),
                                 step.getName(), IRemote(step),
                                 results)


class RemoteBuildStep(pb.Referenceable):

    def __init__(self, step):
        self.s = step

    def remote_getName(self):
        return self.s.getName()

    def remote_getBuild(self):
        return IRemote(self.s.getBuild())

    def remote_getTimes(self):
        return self.s.getTimes()

    def remote_getExpectations(self):
        return self.s.getExpectations()

    def remote_getLogs(self):
        logs = {}
        for log in self.s.getLogs():
            logs[log.getName()] = IRemote(log)
        return logs

    def remote_isFinished(self):
        return self.s.isFinished()

    def remote_waitUntilFinished(self):
        return self.s.waitUntilFinished()  # returns a Deferred

    def remote_getETA(self):
        return self.s.getETA()

    def remote_getText(self):
        return self.s.getText()

    def remote_getResults(self):
        return self.s.getResults()

components.registerAdapter(RemoteBuildStep,
                           interfaces.IBuildStepStatus, IRemote)


class RemoteSlave:

    def __init__(self, slave):
        self.s = slave

    def remote_getName(self):
        return self.s.getName()

    def remote_getAdmin(self):
        return self.s.getAdmin()

    def remote_getHost(self):
        return self.s.getHost()

    def remote_isConnected(self):
        return self.s.isConnected()

components.registerAdapter(RemoteSlave,
                           interfaces.ISlaveStatus, IRemote)


class RemoteEvent:

    def __init__(self, event):
        self.e = event

    def remote_getTimes(self):
        return self.s.getTimes()

    def remote_getText(self):
        return self.s.getText()

components.registerAdapter(RemoteEvent,
                           interfaces.IStatusEvent, IRemote)


class RemoteLog(pb.Referenceable):

    def __init__(self, log):
        self.l = log

    def remote_getName(self):
        return self.l.getName()

    def remote_isFinished(self):
        return self.l.isFinished()

    def remote_waitUntilFinished(self):
        d = self.l.waitUntilFinished()
        d.addCallback(lambda res: self)
        return d

    def remote_getText(self):
        return self.l.getText()

    def remote_getTextWithHeaders(self):
        return self.l.getTextWithHeaders()

    def remote_getChunks(self):
        return self.l.getChunks()
    # TODO: subscription interface

components.registerAdapter(RemoteLog, logfile.LogFile, IRemote)
# TODO: something similar for builder.HTMLLogfile ?


class RemoteChange:

    def __init__(self, change):
        self.c = change

    def getWho(self):
        return self.c.who

    def getFiles(self):
        return self.c.files

    def getComments(self):
        return self.c.comments

components.registerAdapter(RemoteChange, changes.Change, IRemote)


class StatusClientPerspective(base.StatusReceiverPerspective):

    subscribed = None
    client = None

    def __init__(self, status):
        self.status = status  # the IStatus
        self.subscribed_to_builders = []  # Builders to which we're subscribed
        self.subscribed_to = []  # everything else we're subscribed to

    def __getstate__(self):
        d = self.__dict__.copy()
        d['client'] = None
        return d

    def attached(self, mind):
        # twlog.msg("StatusClientPerspective.attached")
        return self

    def detached(self, mind):
        twlog.msg("PB client detached")
        self.client = None
        for name in self.subscribed_to_builders:
            twlog.msg(" unsubscribing from Builder(%s)" % name)
            self.status.getBuilder(name).unsubscribe(self)
        for s in self.subscribed_to:
            twlog.msg(" unsubscribe from %s" % s)
            s.unsubscribe(self)
        self.subscribed = None

    def perspective_subscribe(self, mode, interval, target):
        """The remote client wishes to subscribe to some set of events.
        'target' will be sent remote messages when these events happen.
        'mode' indicates which events are desired: it is a string with one
        of the following values:

        'builders': builderAdded, builderRemoved
        'builds': those plus builderChangedState, buildStarted, buildFinished
        'steps': all those plus buildETAUpdate, stepStarted, stepFinished
        'logs': all those plus stepETAUpdate, logStarted, logFinished
        'full': all those plus logChunk (with the log contents)


        Messages are defined by buildbot.interfaces.IStatusReceiver .
        'interval' is used to specify how frequently ETAUpdate messages
        should be sent.

        Raising or lowering the subscription level will take effect starting
        with the next build or step."""

        assert mode in ("builders", "builds", "steps", "logs", "full")
        assert target
        twlog.msg("PB subscribe(%s)" % mode)

        self.client = target
        self.subscribed = mode
        self.interval = interval
        self.subscribed_to.append(self.status)
        # wait a moment before subscribing, so the new-builder messages
        # won't appear before this remote method finishes
        eventually(self.status.subscribe, self)
        return None

    def perspective_unsubscribe(self):
        twlog.msg("PB unsubscribe")
        self.status.unsubscribe(self)
        self.subscribed_to.remove(self.status)
        self.client = None

    def perspective_getBuildSets(self):
        """This returns tuples of (buildset, bsid), because that is much more
        convenient for tryclient."""
        d = self.status.getBuildSets()

        def make_remotes(buildsets):
            return [(IRemote(s), s.id) for s in buildsets]
        d.addCallback(make_remotes)
        return d

    def perspective_getBuilderNames(self):
        return self.status.getBuilderNames()

    def perspective_getBuilder(self, name):
        b = self.status.getBuilder(name)
        return IRemote(b)

    def perspective_getSlave(self, name):
        s = self.status.getSlave(name)
        return IRemote(s)

    def perspective_ping(self):
        """Ping method to allow pb clients to validate their connections."""
        return "pong"

    # IStatusReceiver methods, invoked if we've subscribed

    # mode >= builder
    def builderAdded(self, name, builder):
        self.client.callRemote("builderAdded", name, IRemote(builder))
        if self.subscribed in ("builds", "steps", "logs", "full"):
            self.subscribed_to_builders.append(name)
            return self
        return None

    def builderChangedState(self, name, state):
        self.client.callRemote("builderChangedState", name, state, None)
        # TODO: remove leftover ETA argument

    def builderRemoved(self, name):
        if name in self.subscribed_to_builders:
            self.subscribed_to_builders.remove(name)
        self.client.callRemote("builderRemoved", name)

    def buildsetSubmitted(self, buildset):
        # TODO: deliver to client, somehow
        pass

    # mode >= builds
    def buildStarted(self, name, build):
        self.client.callRemote("buildStarted", name, IRemote(build))
        if self.subscribed in ("steps", "logs", "full"):
            self.subscribed_to.append(build)
            return (self, self.interval)
        return None

    def buildFinished(self, name, build, results):
        if build in self.subscribed_to:
            # we might have joined during the build
            self.subscribed_to.remove(build)
        self.client.callRemote("buildFinished",
                               name, IRemote(build), results)

    # mode >= steps
    def buildETAUpdate(self, build, eta):
        self.client.callRemote("buildETAUpdate",
                               build.getBuilder().getName(), IRemote(build),
                               eta)

    def stepStarted(self, build, step):
        # we add some information here so the client doesn't have to do an
        # extra round-trip
        self.client.callRemote("stepStarted",
                               build.getBuilder().getName(), IRemote(build),
                               step.getName(), IRemote(step))
        if self.subscribed in ("logs", "full"):
            self.subscribed_to.append(step)
            return (self, self.interval)
        return None

    def stepFinished(self, build, step, results):
        self.client.callRemote("stepFinished",
                               build.getBuilder().getName(), IRemote(build),
                               step.getName(), IRemote(step),
                               results)
        if step in self.subscribed_to:
            # eventually (through some new subscription method) we could
            # join in the middle of the step
            self.subscribed_to.remove(step)

    # mode >= logs
    def stepETAUpdate(self, build, step, ETA, expectations):
        self.client.callRemote("stepETAUpdate",
                               build.getBuilder().getName(), IRemote(build),
                               step.getName(), IRemote(step),
                               ETA, expectations)

    def logStarted(self, build, step, log):
        # TODO: make the HTMLLog adapter
        rlog = IRemote(log, None)
        if not rlog:
            print "hey, couldn't adapt %s to IRemote" % log
        self.client.callRemote("logStarted",
                               build.getBuilder().getName(), IRemote(build),
                               step.getName(), IRemote(step),
                               log.getName(), IRemote(log, None))
        if self.subscribed in ("full",):
            self.subscribed_to.append(log)
            return self
        return None

    def logFinished(self, build, step, log):
        self.client.callRemote("logFinished",
                               build.getBuilder().getName(), IRemote(build),
                               step.getName(), IRemote(step),
                               log.getName(), IRemote(log, None))
        if log in self.subscribed_to:
            self.subscribed_to.remove(log)

    # mode >= full
    def logChunk(self, build, step, log, channel, text):
        self.client.callRemote("logChunk",
                               build.getBuilder().getName(), IRemote(build),
                               step.getName(), IRemote(step),
                               log.getName(), IRemote(log),
                               channel, text)


class PBListener(base.StatusReceiverMultiService):

    """I am a listener for PB-based status clients."""

    compare_attrs = ["port", "cred"]
    implements(portal.IRealm)

    def __init__(self, port, user="statusClient", passwd="clientpw"):
        base.StatusReceiverMultiService.__init__(self)
        if isinstance(port, int):
            port = "tcp:%d" % port
        self.port = port
        self.cred = (user, passwd)
        p = portal.Portal(self)
        c = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        c.addUser(user, passwd)
        p.registerChecker(c)
        f = pb.PBServerFactory(p)
        s = strports.service(port, f)
        s.setServiceParent(self)

    def setServiceParent(self, parent):
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.status = parent

    def requestAvatar(self, avatarID, mind, interface):
        assert interface == pb.IPerspective
        p = StatusClientPerspective(self.status)
        p.attached(mind)  # perhaps .callLater(0) ?
        return (pb.IPerspective, p,
                lambda p=p, mind=mind: p.detached(mind))
