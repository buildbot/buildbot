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

from __future__ import absolute_import
from __future__ import print_function

from twisted.python import log
from twisted.spread import pb


class StatusClient(pb.Referenceable):

    """To use this, call my .connected method with a RemoteReference to the
    buildmaster's StatusClientPerspective object.
    """

    def __init__(self, events):
        self.builders = {}
        self.events = events

    def connected(self, remote):
        log.msg("connected")
        self.remote = remote
        remote.callRemote("subscribe", self.events, 5, self)

    def remote_builderAdded(self, buildername, builder):
        log.msg("builderAdded", buildername)

    def remote_builderRemoved(self, buildername):
        log.msg("builderRemoved", buildername)

    def remote_builderChangedState(self, buildername, state, eta):
        log.msg("builderChangedState", buildername, state, eta)

    def remote_buildStarted(self, buildername, build):
        log.msg("buildStarted", buildername)

    def remote_buildFinished(self, buildername, build, results):
        log.msg("buildFinished", results)

    def remote_buildETAUpdate(self, buildername, build, eta):
        log.msg("ETA", buildername, eta)

    def remote_stepStarted(self, buildername, build, stepname, step):
        log.msg("stepStarted", buildername, stepname)

    def remote_stepFinished(self, buildername, build, stepname, step, results):
        log.msg("stepFinished", buildername, stepname, results)

    def remote_stepETAUpdate(self, buildername, build, stepname, step,
                             eta, expectations):
        log.msg("stepETA", buildername, stepname, eta)

    def remote_logStarted(self, buildername, build, stepname, step,
                          logname, log):
        log.msg("logStarted", buildername, stepname)

    def remote_logFinished(self, buildername, build, stepname, step,
                           logname, log):
        log.msg("logFinished", buildername, stepname)

    def remote_logChunk(self, buildername, build, stepname, step, logname, log,
                        channel, text):
        ChunkTypes = ["STDOUT", "STDERR", "HEADER"]
        log.msg("logChunk[%s]: %s" % (ChunkTypes[channel], text))
