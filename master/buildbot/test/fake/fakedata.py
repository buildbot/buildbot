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

import types

from buildbot.data import connector
from buildbot.test.util import validation
from buildbot.util import json
from twisted.internet import defer
from twisted.python import failure


class FakeUpdates(object):

    # unlike "real" update methods, all of the fake methods are here in a
    # single class.

    def __init__(self, master, testcase):
        self.master = master
        self.testcase = testcase

        # test cases should assert the values here:
        self.changesAdded = []  # Changes are numbered starting at 1.
        self.changesourceIds = {}  # { name : id }; users can add changesources here
        self.buildsetsAdded = []  # Buildsets are numbered starting at 1
        self.maybeBuildsetCompleteCalls = 0
        self.masterStateChanges = []  # dictionaries
        self.schedulerIds = {}  # { name : id }; users can add schedulers here
        self.builderIds = {}  # { name : id }; users can add schedulers here
        self.schedulerMasters = {}  # { schedulerid : masterid }
        self.changesourceMasters = {}  # { changesourceid : masterid }
        self.buildslaveIds = {}  # { name : id }; users can add buildslaves here
        self.logs = {}  # { logid : [ added stuff, None for finish ] }

    # extra assertions

    def assertProperties(self, sourced, properties):
        self.testcase.assertIsInstance(properties, dict)
        for k, v in properties.iteritems():
            self.testcase.assertIsInstance(k, unicode)
            if sourced:
                self.testcase.assertIsInstance(v, tuple)
                self.testcase.assertEqual(len(v), 2)
                propval, propsrc = v
                self.testcase.assertIsInstance(propsrc, unicode)
            else:
                propval = v
            try:
                json.dumps(propval)
            except:
                self.testcase.fail("value for %s is not JSON-able" % (k,))

    # update methods

    def addChange(self, files=None, comments=None, author=None,
                  revision=None, when_timestamp=None, branch=None, category=None,
                  revlink=u'', properties={}, repository=u'', codebase=None,
                  project=u'', src=None):

        # double-check args, types, etc.
        if files is not None:
            self.testcase.assertIsInstance(files, list)
            map(lambda f: self.testcase.assertIsInstance(f, unicode), files)
        self.testcase.assertIsInstance(comments, (types.NoneType, unicode))
        self.testcase.assertIsInstance(author, (types.NoneType, unicode))
        self.testcase.assertIsInstance(revision, (types.NoneType, unicode))
        self.testcase.assertIsInstance(when_timestamp, (types.NoneType, int))
        self.testcase.assertIsInstance(branch, (types.NoneType, unicode))
        self.testcase.assertIsInstance(category, (types.NoneType, unicode))
        self.testcase.assertIsInstance(revlink, (types.NoneType, unicode))
        self.assertProperties(sourced=False, properties=properties)
        self.testcase.assertIsInstance(repository, unicode)
        self.testcase.assertIsInstance(codebase, (types.NoneType, unicode))
        self.testcase.assertIsInstance(project, unicode)
        self.testcase.assertIsInstance(src, (types.NoneType, unicode))

        # use locals() to ensure we get all of the args and don't forget if
        # more are added
        self.changesAdded.append(locals())
        self.changesAdded[-1].pop('self')
        return defer.succeed(len(self.changesAdded))

    def masterActive(self, name, masterid):
        self.testcase.assertIsInstance(name, unicode)
        self.testcase.assertIsInstance(masterid, int)
        if masterid:
            self.testcase.assertEqual(masterid, 1)
        self.masterActive = True
        return defer.succeed(None)

    def masterStopped(self, name, masterid):
        self.testcase.assertIsInstance(name, unicode)
        self.testcase.assertEqual(masterid, 1)
        self.masterActive = False
        return defer.succeed(None)

    def expireMasters(self):
        return defer.succeed(None)

    @defer.inlineCallbacks
    def addBuildset(self, waited_for, scheduler=None, sourcestamps=[], reason='',
                    properties={}, builderNames=[], external_idstring=None):
        # assert types
        self.testcase.assertIsInstance(scheduler, unicode)
        self.testcase.assertIsInstance(sourcestamps, list)
        for ss in sourcestamps:
            if not isinstance(ss, int) and not isinstance(ss, dict):
                self.testcase.fail("%s (%s) is not an integer or a dictionary"
                                   % (ss, type(ss)))
            del ss  # since we use locals(), below
        self.testcase.assertIsInstance(reason, unicode)
        self.assertProperties(sourced=True, properties=properties)
        self.testcase.assertIsInstance(builderNames, list)
        self.testcase.assertIsInstance(external_idstring,
                                       (types.NoneType, unicode))

        self.buildsetsAdded.append(locals())
        self.buildsetsAdded[-1].pop('self')

        # call through to the db layer, since many scheduler tests expect to
        # find the buildset in the db later - TODO fix this!
        bsid, brids = yield self.master.db.buildsets.addBuildset(
            sourcestamps=sourcestamps, reason=reason,
            properties=properties, builderNames=builderNames,
            waited_for=waited_for, external_idstring=external_idstring)
        defer.returnValue((bsid, brids))

    def maybeBuildsetComplete(self, bsid):
        self.maybeBuildsetCompleteCalls += 1
        return defer.succeed(None)

    def updateBuilderList(self, masterid, builderNames):
        self.testcase.assertEqual(masterid, self.master.masterid)
        for n in builderNames:
            self.testcase.assertIsInstance(n, unicode)
        self.builderNames = builderNames
        return defer.succeed(None)

    def masterDeactivated(self, masterid):
        return defer.succeed(None)

    def findSchedulerId(self, name):
        validation.verifyType(self.testcase, 'scheduler name', name,
                              validation.StringValidator())
        if name not in self.schedulerIds:
            self.schedulerIds[name] = max([0] + self.schedulerIds.values()) + 1
        return defer.succeed(self.schedulerIds[name])

    def findChangeSourceId(self, name):
        validation.verifyType(self.testcase, 'changesource name', name,
                              validation.StringValidator())
        if name not in self.changesourceIds:
            self.changesourceIds[name] = max([0] + self.changesourceIds.values()) + 1
        return defer.succeed(self.changesourceIds[name])

    def findBuilderId(self, name):
        validation.verifyType(self.testcase, 'builder name', name,
                              validation.StringValidator())
        if name not in self.builderIds:
            self.builderIds[name] = max([0] + self.builderIds.values()) + 1
        return defer.succeed(self.builderIds[name])

    def trySetSchedulerMaster(self, schedulerid, masterid):
        currentMasterid = self.schedulerMasters.get(schedulerid)
        if isinstance(currentMasterid, Exception):
            return defer.fail(failure.Failure(
                currentMasterid))
        if currentMasterid and masterid is not None:
            return defer.succeed(False)
        self.schedulerMasters[schedulerid] = masterid
        return defer.succeed(True)

    def trySetChangeSourceMaster(self, changesourceid, masterid):
        currentMasterid = self.changesourceMasters.get(changesourceid)
        if isinstance(currentMasterid, Exception):
            return defer.fail(failure.Failure(
                currentMasterid))
        if currentMasterid and masterid is not None:
            return defer.succeed(False)
        self.changesourceMasters[changesourceid] = masterid
        return defer.succeed(True)

    def newBuild(self, builderid, buildrequestid, buildslaveid):
        validation.verifyType(self.testcase, 'builderid', builderid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'buildrequestid', buildrequestid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'buildslaveid', buildslaveid,
                              validation.IntValidator())
        return defer.succeed((10, 1))

    def setBuildStateStrings(self, buildid, state_strings):
        validation.verifyType(self.testcase, 'buildid', buildid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'state_strings', state_strings,
                              validation.ListValidator(validation.StringValidator()))
        return defer.succeed(None)

    def finishBuild(self, buildid, results):
        validation.verifyType(self.testcase, 'buildid', buildid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'results', results,
                              validation.IntValidator())
        return defer.succeed(None)

    def newStep(self, buildid, name):
        validation.verifyType(self.testcase, 'buildid', buildid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name,
                              validation.IdentifierValidator(50))
        return defer.succeed((10, 1))

    def setStepStateStrings(self, stepid, state_strings):
        validation.verifyType(self.testcase, 'stepid', stepid,
                              validation.IntValidator())
        validation.verifyType(self.t, 'state_strings', state_strings,
                              validation.ListValidator(validation.StringValidator()))
        return defer.succeed(None)

    def finishStep(self, stepid, results):
        validation.verifyType(self.testcase, 'stepid', stepid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'results', results,
                              validation.IntValidator())
        return defer.succeed(None)

    def newLog(self, stepid, name, type):
        validation.verifyType(self.testcase, 'stepid', stepid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name,
                              validation.IdentifierValidator(50))
        validation.verifyType(self.testcase, 'type', type,
                              validation.IdentifierValidator(1))
        return defer.succeed(10)

    def finishLog(self, logid):
        validation.verifyType(self.testcase, 'logid', logid,
                              validation.IntValidator())
        self.logs.setdefault(logid, []).append(None)
        return defer.succeed(None)

    def compressLog(self, logid):
        validation.verifyType(self.testcase, 'logid', logid,
                              validation.IntValidator())
        return defer.succeed(None)

    def appendLog(self, logid, content):
        validation.verifyType(self.testcase, 'logid', logid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'content', content,
                              validation.StringValidator())
        self.testcase.assertEqual(content[-1], u'\n')
        self.logs.setdefault(logid, []).append(content)
        return defer.succeed(None)

    def findBuildslaveId(self, name):
        validation.verifyType(self.testcase, 'buildslave name', name,
                              validation.IdentifierValidator(50))
        # this needs to actually get inserted into the db (fake or real) since
        # getBuildslave will get called later
        return self.master.db.buildslaves.findBuildslaveId(name)

    def buildslaveConnected(self, buildslaveid, masterid, slaveinfo):
        return self.master.db.buildslaves.buildslaveConnected(
            buildslaveid=buildslaveid,
            masterid=masterid,
            slaveinfo=slaveinfo)

    def buildslaveDisconnected(self, buildslaveid, masterid):
        return self.master.db.buildslaves.buildslaveDisconnected(
            buildslaveid=buildslaveid,
            masterid=masterid)

    def __getattr__(self, name):
        import traceback
        traceback.print_stack()


class FakeDataConnector(object):
    # FakeDataConnector delegates to the real DataConnector so it can get all
    # of the proper getter and consumer behavior; it overrides all of the
    # relevant updates with fake methods, though.

    def __init__(self, master, testcase):
        self.master = master
        self.updates = FakeUpdates(master, testcase)

        # get, startConsuming, and control are delegated to a real connector,
        # after some additional assertions
        self.realConnector = connector.DataConnector(master)
        self.rtypes = self.realConnector.rtypes

    def _scanModule(self, mod):
        return self.realConnector._scanModule(mod)

    def getEndpoint(self, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.getEndpoint(path)

    def get(self, path, filters=None, fields=None,
            order=None, limit=None, offset=None):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.get(path, filters=filters, fields=fields,
                                      order=order, limit=limit, offset=offset)

    def startConsuming(self, callback, options, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.startConsuming(callback, options, path)

    def control(self, action, args, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.control(action, args, path)
