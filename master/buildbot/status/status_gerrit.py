
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
            print "gerritout:",data
        def errReceived(self, data):
            print "gerriterr:",data
        def processEnded(self, status_object):
            print "gerrit status",status_object

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
            downloads = build.getProperty("downloads")
        except KeyError:
            return
        if downloads == None:
            return
        message, verified, reviewed = self.messageCB(builderName,build,results)
        for download in downloads:
            project, patch = download.split(" ")[:2]
            changeid = patch.split("/")[0]
            command = ["ssh", self.username+"@"+self.gerritserver,"-p", str(self.gerritport),
                       "gerrit","approve",
                       "--project", project,
                       "--message", message ]
            if verified:
                command.extend["--verified",str(verified)]
            if reviewed:
                command.extend["--code-review",str(reviewed)]
            command.append(str(changeid))
            print command
            reactor.spawnProcess(self.LocalPP(self), "ssh", command)

# vim: set ts=4 sts=4 sw=4 et:
