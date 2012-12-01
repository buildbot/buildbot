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


from twisted.spread import pb

class StatusClient(pb.Referenceable):
    """To use this, call my .connected method with a RemoteReference to the
    buildmaster's StatusClientPerspective object.
    """

    def __init__(self, events):
        self.builders = {}
        self.events = events

    def connected(self, remote):
        print "connected"
        self.remote = remote
        remote.callRemote("subscribe", self.events, 5, self)

    def remote_builderAdded(self, buildername, builder):
        print "builderAdded", buildername

    def remote_builderRemoved(self, buildername):
        print "builderRemoved", buildername

    def remote_builderChangedState(self, buildername, state, eta):
        print "builderChangedState", buildername, state, eta

    def remote_buildStarted(self, buildername, build):
        print "buildStarted", buildername

    def remote_buildFinished(self, buildername, build, results):
        print "buildFinished", results

    def remote_buildETAUpdate(self, buildername, build, eta):
        print "ETA", buildername, eta

    def remote_stepStarted(self, buildername, build, stepname, step):
        print "stepStarted", buildername, stepname

    def remote_stepFinished(self, buildername, build, stepname, step, results):
        print "stepFinished", buildername, stepname, results

    def remote_stepETAUpdate(self, buildername, build, stepname, step,
                             eta, expectations):
        print "stepETA", buildername, stepname, eta

    def remote_logStarted(self, buildername, build, stepname, step,
                          logname, log):
        print "logStarted", buildername, stepname

    def remote_logFinished(self, buildername, build, stepname, step,
                           logname, log):
        print "logFinished", buildername, stepname

    def remote_logChunk(self, buildername, build, stepname, step, logname, log,
                        channel, text):
        ChunkTypes = ["STDOUT", "STDERR", "HEADER"]
        print "logChunk[%s]: %s" % (ChunkTypes[channel], text)

