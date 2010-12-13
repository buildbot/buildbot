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

import os

from buildbot.status.base import StatusReceiverMultiService
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol

def defaultMessageCB(buildername, build, results):
    message = "buildbot finished compiling your patchset\n"
    message += "on configuration %s "%(buildername)
    message += "the result is %s\n"%(results)
    message += "more details: http://%s:8010/builders/%s/builds/%d\n"%(os.uname()[1],buildername,build.getNumber())
    return message,0,0

class GerritStatusPush(StatusReceiverMultiService):
    """Event streamer to a gerrit ssh server."""

    def __init__(self, server, username, messageCB=defaultMessageCB, port=29418,
                 **kwargs):
        """
        @server:   server address to be used to push events notifications.
        @username: ssh userid to use to connect to server.
        @messageCB: callable that is called each time a build is finished, and that is used to define the message,
        	    and note depending on the build results
        @port:     ssh port to use to connect to server.
        """
        StatusReceiverMultiService.__init__(self)
        # Parameters.
        self.gerritserver = server
        self.username = username
        self.messageCB = messageCB
        self.gerritport = port

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
        print """Starting up."""
        StatusReceiverMultiService.setServiceParent(self, parent)
        self.status = self.parent.getStatus()
        self.status.subscribe(self)

    def builderAdded(self, name, builder):
        return self # subscribe to this builder

    def buildFinished(self, builderName, build, results):
        """Do the SSH gerrit verify command to the server."""
        try:
            # Gerrit + Repo
            downloads = build.getProperty("repo_downloads")
            downloaded = build.getProperty("repo_downloaded").split(" ")

            if downloads and 2 * len(downloads) == len(downloaded):
                message, verified, reviewed = self.messageCB(builderName, build, results)
                for i in range(0, len(downloads)):
                    project, change1 = downloads[i].split(" ")
                    change2 = downloaded[2 * i]
                    revision = downloaded[2 * i + 1]
                    if change1 == change2:
                        self.sendCodeReview(str(project), revision, message, verified, reviewed)
            return
        except KeyError:
            try:
                # Gerrit + Git
                build.getProperty("gerrit_branch") # used only to verify Gerrit source
                project = build.getProperty("project")
                revision = build.getProperty("got_revision")

                message, verified, reviewed = self.messageCB(builderName, build, results)
                self.sendCodeReview(project, revision, message, verified, reviewed)
                return
            except KeyError:
                return

    def sendCodeReview(self, project, revision, message=None, verified=0, reviewed=0):
        command = ["ssh", self.username + "@" + self.gerritserver, "-p", str(self.gerritport),
                   "gerrit", "review", "--project", project]
        if message:
            command.append("--message '%s'" % message)
        if verified:
            command.extend(["--verified", str(verified)])
        if reviewed:
            command.extend(["--code-review", str(reviewed)])
        command.append(str(revision))
        print command
        reactor.spawnProcess(self.LocalPP(self), "ssh", command)

# vim: set ts=4 sts=4 sw=4 et:
