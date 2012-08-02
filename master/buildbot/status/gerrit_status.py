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
import types
from StringIO import StringIO
import urllib

from zope.interface import implements
from twisted.internet import defer, reactor
from twisted.python import log as twlog
from buildbot import interfaces, util, config
from buildbot.status import base
from buildbot.status.results import FAILURE, SUCCESS, WARNINGS, Results
from twisted.internet.protocol import ProcessProtocol

class GerritStatusPush(base.StatusReceiverMultiService):
    """Event streamer to a gerrit ssh server."""

    def __init__(self, server, username, port=29418, reviewArg=None, buildSetSummary=False,
                 **kwargs):
        """
        @param server:    Gerrit SSH server's address to use for push event notifications.
        @param username:  Gerrit SSH server's username.
        @param port:      Gerrit SSH server's port.
        @param reviewArg: Optional argument that is passed to the callback.

        @type  buildSetSummary: boolean
        @param buildSetSummary: if True, this notifier will only send a summary
                                email when a buildset containing any of its
                                watched builds completes
        """
        base.StatusReceiverMultiService.__init__(self)

        # Parameters.
        self.gerrit_server = server
        self.gerrit_username = username
        self.gerrit_port = port
        self.reviewArg = reviewArg

        self.buildSetSummary = buildSetSummary
        self.buildSetSubscription = None
        self.watched = []
        self.master_status = None

    class LocalPP(ProcessProtocol):
        def __init__(self, status):
            self.status = status

        def outReceived(self, data):
            print "gerritout:", data

        def errReceived(self, data):
            print "gerriterr:", data

        def processEnded(self, status_object):
            if status_object.value.exitCode:
                print "gerrit status: ERROR:", status_object
            else:
                print "gerrit status: OK"

    def setServiceParent(self, parent):
        """
        @type  parent: L{buildbot.master.BuildMaster}
        """
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.master_status = self.parent
        self.master_status.subscribe(self)
        self.master = self.master_status.master

    def startService(self):
        if self.buildSetSummary:
            self.buildSetSubscription = \
            self.master.subscribeToBuildsetCompletions(self.buildsetFinished)
 
        base.StatusReceiverMultiService.startService(self)

    def stopService(self):
        if self.buildSetSubscription is not None:
            self.buildSetSubscription.unsubscribe()
            self.buildSetSubscription = None
            
        return base.StatusReceiverMultiService.stopService(self)

    def disownServiceParent(self):
        self.master_status.unsubscribe(self)
        self.master_status = None
        for w in self.watched:
            w.unsubscribe(self)
        return base.StatusReceiverMultiService.disownServiceParent(self)

    def builderAdded(self, name, builder):
        self.watched.append(builder)
        return self # subscribe to this builder

    def builderRemoved(self, name):
        pass

    def builderChangedState(self, name, state):
        pass

    def buildStarted(self, name, build):
        pass

    def buildFinished(self, name, build, results):
        if ( not self.buildSetSummary ):
            # for testing purposes, buildMessage returns a Deferred that fires
            # when the mail has been sent. To help unit tests, we return that
            # Deferred here even though the normal IStatusReceiver.buildFinished
            # signature doesn't do anything with it. If that changes (if
            # .buildFinished's return value becomes significant), we need to
            # rearrange this.
            return self.buildMessage(name, [build], results)
        return None
    
    def _gotBuilds(self, res, buildset, builders):
        builds = []
        i = 0
        for (builddictlist, buildr) in res:
            builder = builders[i]
            i += 1
            print 1
            print builddictlist
            print 2
            print builder
            for builddict in builddictlist:
                print 3
                print builddict
                build = builder.getBuild(builddict['number'])
                print 4
                print build
                print 5
                print build.getBuilder()
                print 6
                print build.getBuilder().name
                if build is not None:
                    builds.append(build)

        self.buildCodeReview("Buildset Complete: " + buildset['reason'], builds,
                          buildset['results'])
        
    def _gotBuildRequests(self, breqs, buildset):
        dl = []
        builders = []
        for breq in breqs:
            buildername = breq['buildername']
            builder = self.master_status.getBuilder(buildername)
            builders.append(builder)
            print 10
            print builder
            d = self.master.db.builds.getBuildsForRequest(breq['brid'])
            d.addCallback(lambda builddictlist: (builddictlist, builder))
            dl.append(d)
        d = defer.gatherResults(dl)
        d.addCallback(self._gotBuilds, buildset, builders)

    def _gotBuildSet(self, buildset, bsid):
        d = self.master.db.buildrequests.getBuildRequests(bsid=bsid)
        d.addCallback(self._gotBuildRequests, buildset)
        
    def buildsetFinished(self, bsid, result):
        d = self.master.db.buildsets.getBuildset(bsid=bsid)
        d.addCallback(self._gotBuildSet, bsid)
            
        return d

    def buildCodeReview(self, name, builds, results):
        """Do the SSH gerrit verify command to the server."""

        message = ""
        length = len(builds)
        for i in range(0,length):

            # Gerrit + Git
            if builds[i].getProperty("gerrit_branch") is None: # used only to verify Gerrit source
                return
            project = builds[i].getProperty("project")
            revision = builds[i].getProperty("got_revision")
            if project is None or revision is None:
                return
            print builds[i]
            print builds[i].getBuilder()
            print builds[i].getBuilder().name
            tmp = builds[i].getBuilder()
            message += "Build %s\n" % Results[builds[i].results]
            message += ": %s\n" % tmp.name
            if self.reviewArg:
                message += ": %sbuilders/%s/builds/%d\n" % (self.reviewArg, tmp.name, builds[i].getNumber())
            message += "\n\n"

            verified = (results == SUCCESS or -1)
            reviewed = 0

        self.sendCodeReview(project, revision, message, verified, reviewed)
        return

    def sendCodeReview(self, project, revision, message=None, verified=0, reviewed=0):
        command = ["ssh", self.gerrit_username + "@" + self.gerrit_server, "-p %d" % self.gerrit_port,
                   "gerrit", "review", "--project %s" % str(project)]
        if message:
            command.append("--message '%s'" % message.replace("'","\""))
        if verified:
            command.extend(["--verified %d" % int(verified)])
        if reviewed:
            command.extend(["--code-review %d" % int(reviewed)])
        command.append(str(revision))
        print command
        reactor.spawnProcess(self.LocalPP(self), "ssh", command)

