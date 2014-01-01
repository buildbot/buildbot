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

from buildbot.data import base
from buildbot.data import types
from twisted.internet import defer


class LogChunkEndpoint(base.BuildNestingMixin, base.Endpoint):

    # Note that this is a singular endpoint, even though it overrides the
    # offset/limit query params in ResultSpec
    isCollection = False
    pathPatterns = """
        /log/n:logid/content
        /step/n:stepid/log/i:log_slug/content
        /build/n:buildid/step/i:step_name/log/i:log_slug/content
        /build/n:buildid/step/n:step_number/log/i:log_slug/content
        /builder/n:builderid/build/n:build_number/step/i:step_name/log/i:log_slug/content
        /builder/n:builderid/build/n:build_number/step/n:step_number/log/i:log_slug/content
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        # calculate the logid
        if 'logid' in kwargs:
            logid = kwargs['logid']
            dbdict = None
        else:
            stepid = yield self.getStepid(kwargs)
            if stepid is None:
                return
            dbdict = yield self.master.db.logs.getLogBySlug(stepid,
                                                            kwargs.get('log_slug'))
            if not dbdict:
                return
            logid = dbdict['id']

        firstline = resultSpec.offset or 0
        lastline = None if resultSpec.limit is None else firstline + resultSpec.limit - 1
        resultSpec.removePagination()

        # get the number of lines, if necessary
        if lastline is None:
            if not dbdict:
                dbdict = yield self.master.db.logs.getLog(logid)
            if not dbdict:
                return
            lastline = max(0, dbdict['num_lines'] - 1)

        # bounds checks
        if firstline < 0 or lastline < 0 or firstline > lastline:
            return

        logLines = yield self.master.db.logs.getLogLines(
            logid, firstline, lastline)
        defer.returnValue({
            'logid': logid,
            'firstline': firstline,
            'content': logLines})


class LogChunk(base.ResourceType):

    name = "logchunk"
    plural = "logchunks"
    endpoints = [LogChunkEndpoint]
    keyFields = ['stepid', 'logid']

    class EntityType(types.Entity):
        logid = types.Integer()
        firstline = types.Integer()
        content = types.String()
    entityType = EntityType(name)

