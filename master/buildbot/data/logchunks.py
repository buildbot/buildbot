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

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types


class LogChunkEndpointBase(base.BuildNestingMixin, base.Endpoint):

    @defer.inlineCallbacks
    def getLogIdAndDbDictFromKwargs(self, kwargs):
        # calculate the logid
        if 'logid' in kwargs:
            logid = kwargs['logid']
            dbdict = None
        else:
            stepid = yield self.getStepid(kwargs)
            if stepid is None:
                defer.returnValue((None, None))
            dbdict = yield self.master.db.logs.getLogBySlug(stepid,
                                                            kwargs.get('log_slug'))
            if not dbdict:
                defer.returnValue((None, None))
            logid = dbdict['id']

        defer.returnValue((logid, dbdict))


class LogChunkEndpoint(LogChunkEndpointBase):

    # Note that this is a singular endpoint, even though it overrides the
    # offset/limit query params in ResultSpec
    isCollection = False
    pathPatterns = """
        /logs/n:logid/contents
        /steps/n:stepid/logs/i:log_slug/contents
        /builds/n:buildid/steps/i:step_name/logs/i:log_slug/contents
        /builds/n:buildid/steps/n:step_number/logs/i:log_slug/contents
        /builders/n:builderid/builds/n:build_number/steps/i:step_name/logs/i:log_slug/contents
        /builders/n:builderid/builds/n:build_number/steps/n:step_number/logs/i:log_slug/contents
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        logid, dbdict = yield self.getLogIdAndDbDictFromKwargs(kwargs)
        if logid is None:
            return
        firstline = int(resultSpec.offset or 0)
        lastline = None if resultSpec.limit is None else firstline + \
            int(resultSpec.limit) - 1
        resultSpec.removePagination()

        # get the number of lines, if necessary
        if lastline is None:
            if not dbdict:
                dbdict = yield self.master.db.logs.getLog(logid)
            if not dbdict:
                return
            lastline = int(max(0, dbdict['num_lines'] - 1))

        # bounds checks
        if firstline < 0 or lastline < 0 or firstline > lastline:
            return

        logLines = yield self.master.db.logs.getLogLines(
            logid, firstline, lastline)
        defer.returnValue({
            'logid': logid,
            'firstline': firstline,
            'content': logLines})


class RawLogChunkEndpoint(LogChunkEndpointBase):

    # Note that this is a singular endpoint, even though it overrides the
    # offset/limit query params in ResultSpec
    isCollection = False
    isRaw = True
    pathPatterns = """
        /logs/n:logid/raw
        /steps/n:stepid/logs/i:log_slug/raw
        /builds/n:buildid/steps/i:step_name/logs/i:log_slug/raw
        /builds/n:buildid/steps/n:step_number/logs/i:log_slug/raw
        /builders/n:builderid/builds/n:build_number/steps/i:step_name/logs/i:log_slug/raw
        /builders/n:builderid/builds/n:build_number/steps/n:step_number/logs/i:log_slug/raw
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        logid, dbdict = yield self.getLogIdAndDbDictFromKwargs(kwargs)
        if logid is None:
            return

        if not dbdict:
            dbdict = yield self.master.db.logs.getLog(logid)
            if not dbdict:
                return
        lastline = max(0, dbdict['num_lines'] - 1)

        logLines = yield self.master.db.logs.getLogLines(
            logid, 0, lastline)

        if dbdict['type'] == 's':
            logLines = "\n".join([line[1:] for line in logLines.splitlines()])

        defer.returnValue({
            'raw': logLines,
            'mime-type': u'text/html' if dbdict['type'] == 'h' else u'text/plain',
            'filename': dbdict['slug']})


class LogChunk(base.ResourceType):

    name = "logchunk"
    plural = "logchunks"
    endpoints = [LogChunkEndpoint, RawLogChunkEndpoint]
    keyFields = ['stepid', 'logid']

    class EntityType(types.Entity):
        logid = types.Integer()
        firstline = types.Integer()
        content = types.String()
    entityType = EntityType(name)
