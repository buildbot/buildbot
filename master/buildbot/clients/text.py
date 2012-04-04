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

from twisted.spread import pb
from twisted.cred import credentials, error
from twisted.internet import reactor
from buildbot.clients import base

class TextClient:
    def __init__(self, master, events="steps", username="statusClient", passwd="clientpw"):
        """
        @type  master: string
        @param master: a host:port string to masters L{buildbot.status.client.PBListener}

        @type  username: string
        @param username: 

        @type  passwd: string
        @param passwd: 

        @type  events: string, one of builders, builds, steps, logs, full
        @param events: specify what level of detail should be reported.
         - 'builders': only announce new/removed Builders
         - 'builds': also announce builderChangedState, buildStarted, and
           buildFinished
         - 'steps': also announce buildETAUpdate, stepStarted, stepFinished
         - 'logs': also announce stepETAUpdate, logStarted, logFinished
         - 'full': also announce log contents
        """        
        self.master = master
        self.username = username
        self.passwd = passwd
        self.listener = base.StatusClient(events)

    def run(self):
        """Start the TextClient."""
        self.startConnecting()
        reactor.run()

    def startConnecting(self):
        try:
            host, port = re.search(r'(.+):(\d+)', self.master).groups()
            port = int(port)
        except:
            print "unparseable master location '%s'" % self.master
            print " expecting something more like localhost:8007"
            raise
        cf = pb.PBClientFactory()
        creds = credentials.UsernamePassword(self.username, self.passwd)
        d = cf.login(creds)
        reactor.connectTCP(host, port, cf)
        d.addCallbacks(self.connected, self.not_connected)
        return d
    def connected(self, ref):
        ref.notifyOnDisconnect(self.disconnected)
        self.listener.connected(ref)
    def not_connected(self, why):
        if why.check(error.UnauthorizedLogin):
            print """
Unable to login.. are you sure we are connecting to a
buildbot.status.client.PBListener port and not to the slaveport?
"""
        reactor.stop()
        return why
    def disconnected(self, ref):
        print "lost connection"
        # we can get here in one of two ways: the buildmaster has
        # disconnected us (probably because it shut itself down), or because
        # we've been SIGINT'ed. In the latter case, our reactor is already
        # shut down, but we have no easy way of detecting that. So protect
        # our attempt to shut down the reactor.
        try:
            reactor.stop()
        except RuntimeError:
            pass

