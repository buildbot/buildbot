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

from twisted.internet import defer
from buildbot.data import base

class EndpointMixin(object):

    def db2data(self, dbdict):
        data = {
            'logid': dbdict['id'],
            'name': dbdict['name'],
            'stepid': dbdict['stepid'],
            'step_link': base.Link(('step', str(dbdict['stepid']))),
            'complete': dbdict['complete'],
            'num_lines': dbdict['num_lines'],
            'type': dbdict['type'],
            'link': base.Link(('log', str(dbdict['id']))),
        }
        return defer.succeed(data)


class LogEndpoint(EndpointMixin, base.BuildNestingMixin, base.Endpoint):

    pathPatterns = """
        /log/n:logid
        /step/n:stepid/log/i:log_name
        /build/n:buildid/step/i:step_name/log/i:log_name
        /build/n:buildid/step/n:step_number/log/i:log_name
        /builder/n:builderid/build/n:build_number/step/i:step_name/log/i:log_name
        /builder/n:builderid/build/n:build_number/step/n:step_number/log/i:log_name
    """

    @defer.inlineCallbacks
    def get(self, options, kwargs):
        if 'logid' in kwargs:
            dbdict = yield self.master.db.logs.getLog(kwargs['logid'])
            defer.returnValue((yield self.db2data(dbdict))
                                if dbdict else None)
            return

        stepid = yield self.getStepid(kwargs)
        if stepid is None:
            return

        dbdict = yield self.master.db.logs.getLogByName(stepid,
                                            kwargs.get('log_name'))
        defer.returnValue((yield self.db2data(dbdict))
                            if dbdict else None)


class LogContentEndpoint(EndpointMixin, base.BuildNestingMixin, base.Endpoint):

    pathPatterns = """
        /log/n:logid/content
        /step/n:stepid/log/i:log_name/content
        /build/n:buildid/step/i:step_name/log/i:log_name/content
        /build/n:buildid/step/n:step_number/log/i:log_name/content
        /builder/n:builderid/build/n:build_number/step/i:step_name/log/i:log_name/content
        /builder/n:builderid/build/n:build_number/step/n:step_number/log/i:log_name/content
    """

    @defer.inlineCallbacks
    def get(self, options, kwargs):
        # calculate the logid
        if 'logid' in kwargs:
            logid = kwargs['logid']
            dbdict = None
        else:
            stepid = yield self.getStepid(kwargs)
            if stepid is None:
                return
            dbdict = yield self.master.db.logs.getLogByName(stepid,
                                                kwargs.get('log_name'))
            if not dbdict:
                return
            logid = dbdict['id']

        firstline = options.get('firstline', 0)
        lastline = options.get('lastline', None)

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


class LogsEndpoint(EndpointMixin, base.BuildNestingMixin, base.Endpoint):

    pathPatterns = """
        /step/n:stepid/log
        /build/n:buildid/step/i:step_name/log
        /build/n:buildid/step/n:step_number/log
        /builder/n:builderid/build/n:build_number/step/i:step_name/log
        /builder/n:builderid/build/n:build_number/step/n:step_number/log
    """

    @defer.inlineCallbacks
    def get(self, options, kwargs):
        stepid = yield self.getStepid(kwargs)
        if not stepid:
            defer.returnValue([])
            return
        logs = yield self.master.db.logs.getLogs(stepid=stepid)
        defer.returnValue([ (yield self.db2data(dbdict)) for dbdict in logs ])


class LogsResourceType(base.ResourceType):

    type = "step"
    endpoints = [ LogEndpoint, LogContentEndpoint, LogsEndpoint ]
    keyFields = [ 'stepid', 'logid' ]

    @base.updateMethod
    def newLog(self, stepid, name, type):
        return self.master.db.logs.addLog(
                stepid=stepid, name=name, type=type)

    @base.updateMethod
    def finishLog(self, logid):
        return self.master.db.logs.finishLog(logid=logid)

    @base.updateMethod
    def compressLog(self, logid):
        return self.master.db.logs.compressLog(logid=logid)

    @base.updateMethod
    def appendLog(self, logid, content):
        return self.master.db.logs.appendLog(logid=logid, content=content)
