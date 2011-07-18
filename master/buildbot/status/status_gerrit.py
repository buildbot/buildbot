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


"""Push events to gerrit

."""

from buildbot.status.base import StatusReceiverMultiService
from buildbot.status.results import Results, FAILURE
from twisted.internet import reactor, defer
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log

def defaultReviewCB(builderNames, build, result, arg):
    message =  "Buildbot finished compiling your patchset\n"
    message += "on configuration(s): %s\n\n" % ", ".join(builderNames)
    message += "The result is: %s\n" % Results[result].upper()

    # message, verified, reviewed
    return message, (result < FAILURE or -1), 0

class GerritStatusPush(StatusReceiverMultiService):
    """Event streamer to a gerrit ssh server."""

    def __init__(self, server, username, reviewCB=defaultReviewCB, port=29418, reviewArg=None,
                 **kwargs):
        """
        @param server:    Gerrit SSH server's address to use for push event notifications.
        @param username:  Gerrit SSH server's username.
        @param reviewCB:  Callback that is called each time a build is finished, and that is used
                          to define the message and review approvals depending on the build result.
        @param port:      Gerrit SSH server's port.
        @param reviewArg: Optional argument that is passed to the callback.
        """
        StatusReceiverMultiService.__init__(self)
        # Parameters.
        self.gerrit_server = server
        self.gerrit_username = username
        self.gerrit_port = port
        self.reviewCB = reviewCB
        self.reviewArg = reviewArg
        self.sourceStampSubscription = None

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

    def startService(self):
        StatusReceiverMultiService.startService(self)
        self.sourceStampSubscription = \
            self.parent.subscribeToSourceStampCompletions(
                    self.sourceStampFinished)

    def stopService(self):
        if self.sourceStampSubscription is not None:
            self.sourceStampSubscription.unsubscribe()
            self.sourceStampSubscription = None
        return StatusReceiverMultiService.stopService(self)

    def sourceStampFinished(self, ssid, result):
        log.msg("GerritStatusPush: sourcestamp %s finished (status: %s)"
                % (ssid, Results[result]))
        d = self.parent.db.buildrequests.getBuildRequests(ssid=ssid)
        d.addCallback(self._gotBuildRequests, result)
        return d

    def _gotBuildRequests(self, breqs, result):
        dl = []
        for breq in breqs:
            builder = self.parent.getStatus().getBuilder(breq['buildername'])
            d = self.parent.db.builds.getBuildsForRequest(breq['brid'])
            d.addCallback(lambda *a: a, builder) # tuple(build, builder)
            dl.append(d)
        d = defer.DeferredList(dl)
        d.addCallback(self._gotBuilds, result)

    def _gotBuilds(self, dl_result, result):
        builderNames = set()
        builds = []
        for (success, build_tuple) in dl_result:
            builddictlist, builder = build_tuple
            builderNames.add(builder.name)
            for builddict in builddictlist:
                build = builder.getBuild(builddict['number'])
                if not build:
                    log.msg("GerritStatusPush: did not find build num %s on "
                            "builder %s" % (builddict['number'], builder.name))
                    continue
                builds.append(build)

        if not builds:
            log.msg("GerritStatusPush: no builds")
            return

        builderNames = list(builderNames)
        builderNames.sort()

        if "repo_downloads" in builds[0].properties:
            return self._repoBuildsFinished(builds, builderNames, result)
        elif "gerrit_branch" in builds[0].properties:
            return self._gerritBuildsFinished(builds, builderNames, result)
        else:
            log.msg("The build %s does not seem to come from Gerrit"
                    % builds[0])

    def _repoBuildsFinished(self, builds, builderNames, result):
        try:
            downloads = builds[0].getProperty("repo_downloads")
            downloaded = builds[0].getProperty("repo_downloaded").split(" ")
        except KeyError, e:
            log.err(e)
            return
        if not downloads or 2 * len(downloads) != len(downloaded):
            return
        message, verified, reviewed = self.reviewCB(builderNames, builds,
                                                    result, self.reviewArg)
        for i in range(0, len(downloads)):
            try:
                project, change1 = downloads[i].split(" ")
            except ValueError:
                return # something is wrong, abort
            change2 = downloaded[2 * i]
            revision = downloaded[2 * i + 1]
            if change1 == change2:
                self.sendCodeReview(project, revision, message, verified,
                                    reviewed)
            else:
                return # something is wrong, abort

    def _gerritBuildsFinished(self, builds, builderNames, result):
        try:
            project = builds[0].getProperty("project")
            revision = builds[0].getProperty("got_revision")
        except KeyError, e:
            log.err(e)
            return
        message, verified, reviewed = self.reviewCB(
                builderNames, builds, result, self.reviewArg)
        self.sendCodeReview(project, revision, message, verified, reviewed)

    def sendCodeReview(self, project, revision, message=None, verified=0, reviewed=0):
        """Do the SSH gerrit verify command to the server."""
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

# vim: set ts=4 sts=4 sw=4 et:
