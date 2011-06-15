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
from buildbot.status.builder import Results
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol

def defaultReviewCB(builderName, build, result, arg):
    message =  "Buildbot finished compiling your patchset\n"
    message += "on configuration: %s\n" % builderName
    message += "The result is: %s\n" % Results[result].upper()

    # message, verified, reviewed
    return message, (result == 0 or -1), 0

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
        print """Starting up."""
        StatusReceiverMultiService.startService(self)
        self.status = self.parent.getStatus()
        self.status.subscribe(self)

    def builderAdded(self, name, builder):
        return self # subscribe to this builder

    def buildFinished(self, builderName, build, result):
        """Do the SSH gerrit verify command to the server."""
        repo, git = False, False

        # Gerrit + Repo
        try:
            downloads = build.getProperty("repo_downloads")
            downloaded = build.getProperty("repo_downloaded").split(" ")
            repo = True
        except KeyError:
            pass

        if repo:
            if downloads and 2 * len(downloads) == len(downloaded):
                message, verified, reviewed = self.reviewCB(builderName, build, result, self.reviewArg)
                for i in range(0, len(downloads)):
                    try:
                        project, change1 = downloads[i].split(" ")
                    except ValueError:
                        return # something is wrong, abort
                    change2 = downloaded[2 * i]
                    revision = downloaded[2 * i + 1]
                    if change1 == change2:
                        self.sendCodeReview(project, revision, message, verified, reviewed)
                    else:
                        return # something is wrong, abort
            return

        # Gerrit + Git
        try:
            build.getProperty("gerrit_branch") # used only to verify Gerrit source
            project = build.getProperty("project")
            revision = build.getProperty("got_revision")
            git = True
        except KeyError:
            pass

        if git:
            message, verified, reviewed = self.reviewCB(builderName, build, result, self.reviewArg)
            self.sendCodeReview(project, revision, message, verified, reviewed)
            return

    def sendCodeReview(self, project, revision, message=None, verified=0, reviewed=0):
        command = ["ssh", self.gerrit_username + "@" + self.gerrit_server, "-p %d" % self.gerrit_port,
                   "gerrit", "review", "--project %s" % str(project)]
        if message:
            command.append("--message '%s'" % message)
        if verified:
            command.extend(["--verified %d" % int(verified)])
        if reviewed:
            command.extend(["--code-review %d" % int(reviewed)])
        command.append(str(revision))
        print command
        reactor.spawnProcess(self.LocalPP(self), "ssh", command)

# vim: set ts=4 sts=4 sw=4 et:
