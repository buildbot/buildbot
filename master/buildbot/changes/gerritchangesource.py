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

from twisted.internet import reactor

from buildbot.changes import base, changes
from buildbot.util import json
from twisted.internet.protocol import ProcessProtocol

class GerritChangeSource(base.ChangeSource):
    """This source will maintain a connection to gerrit ssh server
    that will provide us gerrit events in json format."""

    compare_attrs = ["gerritserver", "gerritport"]

    parent = None # filled in when we're added
    running = False

    def __init__(self, gerritserver, username, gerritport=29418):
        """
        @type  gerritserver: string
        @param gerritserver: the dns or ip that host the gerrit ssh server,

        @type  gerritport: int
        @param gerritport: the port of the gerrit ssh server,

        @type  username: string
        @param username: the username to use to connect to gerrit

        """

        self.gerritserver = gerritserver
        self.gerritport = gerritport
        self.username = username

    class LocalPP(ProcessProtocol):
        def __init__(self, change_source):
            self.change_source = change_source
            self.data = ""

        def outReceived(self, data):
            """Do line buffering."""
            self.data += data
            lines = self.data.split("\n")
            self.data = lines.pop(-1) # last line is either empty or incomplete
            for line in lines:
                print "gerrit:", line
                self.change_source.lineReceived(line)

        def errReceived(self, data):
            print "gerriterr:", data

        def processEnded(self, status_object):
            self.change_source.startService()

    def lineReceived(self, line):
        try:
            event = json.loads(line)
        except ValueError:
            print "bad json line:", line
            return

        if type(event) == type({}) and "type" in event:
            if event["type"] in [u"change-merged", u"patchset-created"]:
                # flatten the event dictionary, for easy access with WithProperties
                def flatten(event, base, d):
                    for k, v in d.items():
                        if type(v) == dict:
                            flatten(event, base + "." + k, v)
                        else: # already there
                            event[base + "." + k] = v

                properties = {}
                flatten(properties, "event", event)

                change = event["change"]
                patchset = event["patchSet"]

                c = changes.Change(who="%s <%s>" % (change["owner"]["name"], change["owner"]["email"]),
                                   project=change["project"],
                                   branch=change["branch"],
                                   revision=patchset["revision"],
                                   revlink=change["url"],
                                   comments=change["subject"],
                                   files=["unknown"],
                                   properties=properties)
                self.parent.addChange(c)

    def startService(self):
        self.running = True
        self.process = reactor.spawnProcess(self.LocalPP(self), "ssh", ["ssh", self.username+"@"+self.gerritserver,"-p", str(self.gerritport), "gerrit","stream-events"])

    def stopService(self):
        self.running = False
        self.process.signalProcess("KILL")
        return base.ChangeSource.stopService(self)

    def describe(self):
        status = ""
        if not self.running:
            status = "[STOPPED - check log]"
        str = 'GerritChangeSource watching the remote gerrit repository %s %s' \
                % (self.gerritserver, status)
        return str

