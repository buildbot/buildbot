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

import time

from buildbot.status import buildset
from buildbot.status.base import StatusReceiverMultiService
from buildbot.status.builder import EXCEPTION
from buildbot.status.builder import FAILURE
from buildbot.status.builder import RETRY
from buildbot.status.builder import Results
from buildbot.status.builder import SUCCESS
from buildbot.status.builder import WARNINGS
from distutils.version import LooseVersion
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol

# Cache the version that the gerrit server is running for this many seconds
GERRIT_VERSION_CACHE_TIMEOUT = 600


def defaultReviewCB(builderName, build, result, status, arg):
    if result == RETRY:
        return None, 0, 0

    message = "Buildbot finished compiling your patchset\n"
    message += "on configuration: %s\n" % builderName
    message += "The result is: %s\n" % Results[result].upper()

    # message, verified, reviewed
    return message, (result == SUCCESS or -1), 0


def defaultSummaryCB(buildInfoList, results, status, arg):
    success = False
    failure = False

    msgs = []

    for buildInfo in buildInfoList:
        msg = "Builder %(name)s %(resultText)s (%(text)s)" % buildInfo
        link = buildInfo.get('url', None)
        if link:
            msg += " - " + link
        else:
            msg += "."
        msgs.append(msg)

        if buildInfo['result'] == SUCCESS:
            success = True
        else:
            failure = True

    msg = '\n\n'.join(msgs)

    if success and not failure:
        verified = 1
    else:
        verified = -1

    reviewed = 0
    return (msg, verified, reviewed)


# These are just sentinel values for GerritStatusPush.__init__ args
class DEFAULT_REVIEW(object):
    pass


class DEFAULT_SUMMARY(object):
    pass


class GerritStatusPush(StatusReceiverMultiService, buildset.BuildSetSummaryNotifierMixin):

    """Event streamer to a gerrit ssh server."""

    def __init__(self, server, username, reviewCB=DEFAULT_REVIEW,
                 startCB=None, port=29418, reviewArg=None,
                 startArg=None, summaryCB=DEFAULT_SUMMARY, summaryArg=None, **kwargs):
        """
        @param server:    Gerrit SSH server's address to use for push event notifications.
        @param username:  Gerrit SSH server's username.
        @param reviewCB:  Callback that is called each time a build is finished, and that is used
                          to define the message and review approvals depending on the build result.
        @param startCB:   Callback that is called each time a build is started.
                          Used to define the message sent to Gerrit.
        @param port:      Gerrit SSH server's port.
        @param reviewArg: Optional argument passed to the review callback.
        @param startArg:  Optional argument passed to the start callback.
        @param summaryCB:  Callback that is called each time a buildset finishes, and that is used
                           to define a message and review approvals depending on the build result.
        @param summaryArg: Optional argument passed to the summary callback.
        """
        StatusReceiverMultiService.__init__(self)

        # If neither reviewCB nor summaryCB were specified, default to sending
        # out "summary" reviews. But if we were given a reviewCB and only a
        # reviewCB, disable the "summary" reviews, so we don't send out both
        # by default.
        if reviewCB is DEFAULT_REVIEW and summaryCB is DEFAULT_SUMMARY:
            reviewCB = None
            summaryCB = defaultSummaryCB
        if reviewCB is DEFAULT_REVIEW:
            reviewCB = None
        if summaryCB is DEFAULT_SUMMARY:
            summaryCB = None

        # Parameters.
        self.gerrit_server = server
        self.gerrit_username = username
        self.gerrit_port = port
        self.gerrit_version = None
        self.gerrit_version_time = 0
        self.reviewCB = reviewCB
        self.reviewArg = reviewArg
        self.startCB = startCB
        self.startArg = startArg
        self.summaryCB = summaryCB
        self.summaryArg = summaryArg

    def _gerritCmd(self, *args):
        return ["ssh", self.gerrit_username + "@" + self.gerrit_server, "-p %d" % self.gerrit_port, "gerrit"] + list(args)

    class VersionPP(ProcessProtocol):

        def __init__(self, func):
            self.func = func
            self.gerrit_version = None

        def outReceived(self, data):
            vstr = "gerrit version "
            if not data.startswith(vstr):
                print "Error: Cannot interpret gerrit version info:", data
                return
            vers = data[len(vstr):]
            print "gerrit version:", vers
            self.gerrit_version = LooseVersion(vers)

        def errReceived(self, data):
            print "gerriterr:", data

        def processEnded(self, status_object):
            if status_object.value.exitCode:
                print "gerrit version status: ERROR:", status_object
                return
            if self.gerrit_version:
                self.func(self.gerrit_version)

    def getCachedVersion(self):
        if self.gerrit_version is None:
            return None
        if time.time() - self.gerrit_version_time > GERRIT_VERSION_CACHE_TIMEOUT:
            # cached version has expired
            self.gerrit_version = None
        return self.gerrit_version

    def processVersion(self, gerrit_version, func):
        self.gerrit_version = gerrit_version
        self.gerrit_version_time = time.time()
        func()

    def callWithVersion(self, func):
        command = self._gerritCmd("version")
        callback = lambda gerrit_version: self.processVersion(gerrit_version, func)

        reactor.spawnProcess(self.VersionPP(callback), command[0], command)

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
        StatusReceiverMultiService.setServiceParent(self, parent)
        self.master_status = self.parent
        self.master_status.subscribe(self)
        self.master = self.master_status.master

    def startService(self):
        print """Starting up."""
        if self.summaryCB:
            self.summarySubscribe()

        StatusReceiverMultiService.startService(self)

    def stopService(self):
        self.summaryUnsubscribe()

    def builderAdded(self, name, builder):
        return self  # subscribe to this builder

    def buildStarted(self, builderName, build):
        if self.startCB is not None:
            message = self.startCB(builderName, build, self.startArg)
            self.sendCodeReviews(build, message)

    def buildFinished(self, builderName, build, result):
        """Do the SSH gerrit verify command to the server."""
        if self.reviewCB:
            message, verified, reviewed = self.reviewCB(builderName, build, result, self.master_status, self.reviewArg)
            self.sendCodeReviews(build, message, verified, reviewed)

    def sendBuildSetSummary(self, buildset, builds):
        if self.summaryCB:
            def getBuildInfo(build):
                result = build.getResults()
                resultText = {
                    SUCCESS: "succeeded",
                    FAILURE: "failed",
                    WARNINGS: "completed with warnings",
                    EXCEPTION: "encountered an exception",
                }.get(result, "completed with unknown result %d" % result)

                return {'name': build.getBuilder().getName(),
                        'result': result,
                        'resultText': resultText,
                        'text': ' '.join(build.getText()),
                        'url': self.master_status.getURLForThing(build),
                        }
            buildInfoList = sorted([getBuildInfo(build) for build in builds], key=lambda bi: bi['name'])

            message, verified, reviewed = self.summaryCB(buildInfoList, Results[buildset['results']], self.master_status, self.summaryArg)
            self.sendCodeReviews(builds[0], message, verified, reviewed)

    def sendCodeReviews(self, build, message, verified=0, reviewed=0):
        if message is None:
            return

        # Gerrit + Repo
        downloads = build.getProperty("repo_downloads")
        downloaded = build.getProperty("repo_downloaded")
        if downloads is not None and downloaded is not None:
            downloaded = downloaded.split(" ")
            if downloads and 2 * len(downloads) == len(downloaded):
                for i in range(0, len(downloads)):
                    try:
                        project, change1 = downloads[i].split(" ")
                    except ValueError:
                        return  # something is wrong, abort
                    change2 = downloaded[2 * i]
                    revision = downloaded[2 * i + 1]
                    if change1 == change2:
                        self.sendCodeReview(project, revision, message, verified, reviewed)
                    else:
                        return  # something is wrong, abort
            return

        # Gerrit + Git
        if build.getProperty("gerrit_branch") is not None:  # used only to verify Gerrit source
            project = build.getProperty("project")
            revision = build.getProperty("got_revision")

            # review doesn't really work with multiple revisions, so let's
            # just assume it's None there
            if isinstance(revision, dict):
                revision = None

            if project is not None and revision is not None:
                self.sendCodeReview(project, revision, message, verified, reviewed)
                return

    def sendCodeReview(self, project, revision, message=None, verified=0, reviewed=0):
        gerrit_version = self.getCachedVersion()
        if (verified or reviewed) and gerrit_version is None:
            self.callWithVersion(lambda: self.sendCodeReview(project, revision, message, verified, reviewed))
            return

        command = self._gerritCmd("review", "--project %s" % str(project))
        if message:
            command.append("--message '%s'" % message.replace("'", "\""))

        if verified:
            assert(gerrit_version)
            if gerrit_version < LooseVersion("2.6"):
                command.extend(["--verified %d" % int(verified)])
            else:
                command.extend(["--label Verified=%d" % int(verified)])

        if reviewed:
            assert(gerrit_version)
            if gerrit_version < LooseVersion("2.6"):
                command.extend(["--code-review %d" % int(reviewed)])
            else:
                command.extend(["--label Code-Review=%d" % int(reviewed)])

        command.append(str(revision))
        print command
        reactor.spawnProcess(self.LocalPP(self), command[0], command)

# vim: set ts=4 sts=4 sw=4 et:
