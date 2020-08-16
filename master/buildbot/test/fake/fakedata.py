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

import json

from twisted.internet import defer
from twisted.python import failure

from buildbot.data import connector
from buildbot.db.buildrequests import AlreadyClaimedError
from buildbot.test.util import validation
from buildbot.util import service


class FakeUpdates(service.AsyncService):

    # unlike "real" update methods, all of the fake methods are here in a
    # single class.

    def __init__(self, testcase):
        self.testcase = testcase

        # test cases should assert the values here:
        self.changesAdded = []  # Changes are numbered starting at 1.
        # { name : id }; users can add changesources here
        self.changesourceIds = {}
        self.buildsetsAdded = []  # Buildsets are numbered starting at 1
        self.maybeBuildsetCompleteCalls = 0
        self.masterStateChanges = []  # dictionaries
        self.schedulerIds = {}  # { name : id }; users can add schedulers here
        self.builderIds = {}  # { name : id }; users can add schedulers here
        self.schedulerMasters = {}  # { schedulerid : masterid }
        self.changesourceMasters = {}  # { changesourceid : masterid }
        self.workerIds = {}  # { name : id }; users can add workers here
        # { logid : {'finished': .., 'name': .., 'type': .., 'content': [ .. ]} }
        self.logs = {}
        self.claimedBuildRequests = set([])
        self.stepStateString = {}  # { stepid : string }
        self.stepUrls = {}  # { stepid : [(name,url)] }
        self.properties = []
        self.missingWorkers = []
        # extra assertions

    def assertProperties(self, sourced, properties):
        self.testcase.assertIsInstance(properties, dict)
        for k, v in properties.items():
            self.testcase.assertIsInstance(k, str)
            if sourced:
                self.testcase.assertIsInstance(v, tuple)
                self.testcase.assertEqual(len(v), 2)
                propval, propsrc = v
                self.testcase.assertIsInstance(propsrc, str)
            else:
                propval = v
            try:
                json.dumps(propval)
            except (TypeError, ValueError):
                self.testcase.fail("value for {} is not JSON-able".format(k))

    # update methods

    def addChange(self, files=None, comments=None, author=None, committer=None,
                  revision=None, when_timestamp=None, branch=None, category=None,
                  revlink='', properties=None, repository='', codebase=None,
                  project='', src=None):
        if properties is None:
            properties = {}

        # double-check args, types, etc.
        if files is not None:
            self.testcase.assertIsInstance(files, list)
            map(lambda f: self.testcase.assertIsInstance(f, str), files)
        self.testcase.assertIsInstance(comments, (type(None), str))
        self.testcase.assertIsInstance(author, (type(None), str))
        self.testcase.assertIsInstance(committer, (type(None), str))
        self.testcase.assertIsInstance(revision, (type(None), str))
        self.testcase.assertIsInstance(when_timestamp, (type(None), int))
        self.testcase.assertIsInstance(branch, (type(None), str))

        if callable(category):
            pre_change = self.master.config.preChangeGenerator(author=author,
                                                               committer=committer,
                                                               files=files,
                                                               comments=comments,
                                                               revision=revision,
                                                               when_timestamp=when_timestamp,
                                                               branch=branch,
                                                               revlink=revlink,
                                                               properties=properties,
                                                               repository=repository,
                                                               project=project)
            category = category(pre_change)

        self.testcase.assertIsInstance(category, (type(None), str))
        self.testcase.assertIsInstance(revlink, (type(None), str))
        self.assertProperties(sourced=False, properties=properties)
        self.testcase.assertIsInstance(repository, str)
        self.testcase.assertIsInstance(codebase, (type(None), str))
        self.testcase.assertIsInstance(project, str)
        self.testcase.assertIsInstance(src, (type(None), str))

        # use locals() to ensure we get all of the args and don't forget if
        # more are added
        self.changesAdded.append(locals())
        self.changesAdded[-1].pop('self')
        return defer.succeed(len(self.changesAdded))

    def masterActive(self, name, masterid):
        self.testcase.assertIsInstance(name, str)
        self.testcase.assertIsInstance(masterid, int)
        if masterid:
            self.testcase.assertEqual(masterid, 1)
        self.thisMasterActive = True
        return defer.succeed(None)

    def masterStopped(self, name, masterid):
        self.testcase.assertIsInstance(name, str)
        self.testcase.assertEqual(masterid, 1)
        self.thisMasterActive = False
        return defer.succeed(None)

    def expireMasters(self, forceHouseKeeping=False):
        return defer.succeed(None)

    @defer.inlineCallbacks
    def addBuildset(self, waited_for, scheduler=None, sourcestamps=None, reason='',
                    properties=None, builderids=None, external_idstring=None,
                    parent_buildid=None, parent_relationship=None):
        if sourcestamps is None:
            sourcestamps = []
        if properties is None:
            properties = {}
        if builderids is None:
            builderids = []
        # assert types
        self.testcase.assertIsInstance(scheduler, str)
        self.testcase.assertIsInstance(sourcestamps, list)
        for ss in sourcestamps:
            if not isinstance(ss, int) and not isinstance(ss, dict):
                self.testcase.fail("{} ({}) is not an integer or a dictionary".format(ss, type(ss)))
            del ss  # since we use locals(), below
        self.testcase.assertIsInstance(reason, str)
        self.assertProperties(sourced=True, properties=properties)
        self.testcase.assertIsInstance(builderids, list)
        self.testcase.assertIsInstance(external_idstring,
                                       (type(None), str))

        self.buildsetsAdded.append(locals())
        self.buildsetsAdded[-1].pop('self')

        # call through to the db layer, since many scheduler tests expect to
        # find the buildset in the db later - TODO fix this!
        bsid, brids = yield self.master.db.buildsets.addBuildset(
            sourcestamps=sourcestamps, reason=reason,
            properties=properties, builderids=builderids,
            waited_for=waited_for, external_idstring=external_idstring,
            parent_buildid=parent_buildid, parent_relationship=parent_relationship)
        return (bsid, brids)

    def maybeBuildsetComplete(self, bsid):
        self.maybeBuildsetCompleteCalls += 1
        return defer.succeed(None)

    @defer.inlineCallbacks
    def claimBuildRequests(self, brids, claimed_at=None):
        validation.verifyType(self.testcase, 'brids', brids,
                              validation.ListValidator(validation.IntValidator()))
        validation.verifyType(self.testcase, 'claimed_at', claimed_at,
                              validation.NoneOk(validation.DateTimeValidator()))
        if not brids:
            return True
        try:
            yield self.master.db.buildrequests.claimBuildRequests(
                brids=brids, claimed_at=claimed_at)
        except AlreadyClaimedError:
            return False
        self.claimedBuildRequests.update(set(brids))
        return True

    @defer.inlineCallbacks
    def unclaimBuildRequests(self, brids):
        validation.verifyType(self.testcase, 'brids', brids,
                              validation.ListValidator(validation.IntValidator()))
        self.claimedBuildRequests.difference_update(set(brids))
        if brids:
            yield self.master.db.buildrequests.unclaimBuildRequests(brids)

    def completeBuildRequests(self, brids, results, complete_at=None):
        validation.verifyType(self.testcase, 'brids', brids,
                              validation.ListValidator(validation.IntValidator()))
        validation.verifyType(self.testcase, 'results', results,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'complete_at', complete_at,
                              validation.NoneOk(validation.DateTimeValidator()))
        return defer.succeed(True)

    def rebuildBuildrequest(self, buildrequest):
        return defer.succeed(None)

    def updateBuilderList(self, masterid, builderNames):
        self.testcase.assertEqual(masterid, self.master.masterid)
        for n in builderNames:
            self.testcase.assertIsInstance(n, str)
        self.builderNames = builderNames
        return defer.succeed(None)

    def updateBuilderInfo(self, builderid, description, tags):
        yield self.master.db.builders.updateBuilderInfo(builderid, description, tags)

    def masterDeactivated(self, masterid):
        return defer.succeed(None)

    def findSchedulerId(self, name):
        return self.master.db.schedulers.findSchedulerId(name)

    def forget_about_it(self, name):
        validation.verifyType(self.testcase, 'scheduler name', name,
                              validation.StringValidator())
        if name not in self.schedulerIds:
            self.schedulerIds[name] = max(
                [0] + list(self.schedulerIds.values())) + 1
        return defer.succeed(self.schedulerIds[name])

    def findChangeSourceId(self, name):
        validation.verifyType(self.testcase, 'changesource name', name,
                              validation.StringValidator())
        if name not in self.changesourceIds:
            self.changesourceIds[name] = max(
                [0] + list(self.changesourceIds.values())) + 1
        return defer.succeed(self.changesourceIds[name])

    def findBuilderId(self, name):
        validation.verifyType(self.testcase, 'builder name', name,
                              validation.StringValidator())
        return self.master.db.builders.findBuilderId(name)

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

    def addBuild(self, builderid, buildrequestid, workerid):
        validation.verifyType(self.testcase, 'builderid', builderid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'buildrequestid', buildrequestid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'workerid', workerid,
                              validation.IntValidator())
        return defer.succeed((10, 1))

    def generateNewBuildEvent(self, buildid):
        validation.verifyType(self.testcase, 'buildid', buildid,
                              validation.IntValidator())
        return defer.succeed(None)

    def setBuildStateString(self, buildid, state_string):
        validation.verifyType(self.testcase, 'buildid', buildid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'state_string', state_string,
                              validation.StringValidator())
        return defer.succeed(None)

    def finishBuild(self, buildid, results):
        validation.verifyType(self.testcase, 'buildid', buildid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'results', results,
                              validation.IntValidator())
        return defer.succeed(None)

    def setBuildProperty(self, buildid, name, value, source):
        validation.verifyType(self.testcase, 'buildid', buildid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name,
                              validation.StringValidator())
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            self.testcase.fail("Value for {} is not JSON-able".format(name))
        validation.verifyType(self.testcase, 'source', source,
                              validation.StringValidator())
        return defer.succeed(None)

    @defer.inlineCallbacks
    def setBuildProperties(self, buildid, properties):
        for k, v, s in properties.getProperties().asList():
            self.properties.append((buildid, k, v, s))
            yield self.setBuildProperty(buildid, k, v, s)

    def addStep(self, buildid, name):
        validation.verifyType(self.testcase, 'buildid', buildid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name,
                              validation.IdentifierValidator(50))
        return defer.succeed((10, 1, name))

    def addStepURL(self, stepid, name, url):
        validation.verifyType(self.testcase, 'stepid', stepid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name,
                              validation.StringValidator())
        validation.verifyType(self.testcase, 'url', url,
                              validation.StringValidator())
        self.stepUrls.setdefault(stepid, []).append((name, url))
        return defer.succeed(None)

    def startStep(self, stepid):
        validation.verifyType(self.testcase, 'stepid', stepid,
                              validation.IntValidator())
        return defer.succeed(None)

    def setStepStateString(self, stepid, state_string):
        validation.verifyType(self.testcase, 'stepid', stepid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'state_string', state_string,
                              validation.StringValidator())
        self.stepStateString[stepid] = state_string
        return defer.succeed(None)

    def finishStep(self, stepid, results, hidden):
        validation.verifyType(self.testcase, 'stepid', stepid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'results', results,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'hidden', hidden,
                              validation.BooleanValidator())
        return defer.succeed(None)

    def addLog(self, stepid, name, type):
        validation.verifyType(self.testcase, 'stepid', stepid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name,
                              validation.StringValidator())
        validation.verifyType(self.testcase, 'type', type,
                              validation.IdentifierValidator(1))
        logid = max([0] + list(self.logs)) + 1
        self.logs[logid] = dict(
            name=name, type=type, content=[], finished=False)
        return defer.succeed(logid)

    def finishLog(self, logid):
        validation.verifyType(self.testcase, 'logid', logid,
                              validation.IntValidator())
        self.logs[logid]['finished'] = True
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
        self.testcase.assertEqual(content[-1], '\n')
        self.logs[logid]['content'].append(content)
        return defer.succeed(None)

    def findWorkerId(self, name):
        validation.verifyType(self.testcase, 'worker name', name,
                              validation.IdentifierValidator(50))
        # this needs to actually get inserted into the db (fake or real) since
        # getWorker will get called later
        return self.master.db.workers.findWorkerId(name)

    def workerConnected(self, workerid, masterid, workerinfo):
        return self.master.db.workers.workerConnected(
            workerid=workerid,
            masterid=masterid,
            workerinfo=workerinfo)

    def workerConfigured(self, workerid, masterid, builderids):
        return self.master.db.workers.workerConfigured(
            workerid=workerid,
            masterid=masterid,
            builderids=builderids)

    def workerDisconnected(self, workerid, masterid):
        return self.master.db.workers.workerDisconnected(
            workerid=workerid,
            masterid=masterid)

    def deconfigureAllWorkersForMaster(self, masterid):
        return self.master.db.workers.deconfigureAllWorkersForMaster(
            masterid=masterid)

    def workerMissing(self, workerid, masterid, last_connection, notify):
        self.missingWorkers.append((workerid, masterid, last_connection, notify))

    def schedulerEnable(self, schedulerid, v):
        return self.master.db.schedulers.enable(schedulerid, v)

    def setWorkerState(self, workerid, paused, graceful):
        return self.master.db.workers.setWorkerState(
            workerid=workerid,
            paused=paused,
            graceful=graceful)

    # methods form BuildData resource
    @defer.inlineCallbacks
    def setBuildData(self, buildid, name, value, source):
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name, validation.StringValidator())
        validation.verifyType(self.testcase, 'value', value, validation.BinaryValidator())
        validation.verifyType(self.testcase, 'source', source, validation.StringValidator())
        yield self.master.db.build_data.setBuildData(buildid, name, value, source)

    # methods from TestResultSet resource
    @defer.inlineCallbacks
    def addTestResultSet(self, builderid, buildid, stepid, description, category, value_unit):
        validation.verifyType(self.testcase, 'builderid', builderid, validation.IntValidator())
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(self.testcase, 'stepid', stepid, validation.IntValidator())
        validation.verifyType(self.testcase, 'description', description,
                              validation.StringValidator())
        validation.verifyType(self.testcase, 'category', category, validation.StringValidator())
        validation.verifyType(self.testcase, 'value_unit', value_unit, validation.StringValidator())

        test_result_setid = \
            yield self.master.db.test_result_sets.addTestResultSet(builderid, buildid, stepid,
                                                                   description, category,
                                                                   value_unit)
        return test_result_setid

    @defer.inlineCallbacks
    def completeTestResultSet(self, test_result_setid, tests_passed=None, tests_failed=None):
        validation.verifyType(self.testcase, 'test_result_setid', test_result_setid,
                              validation.IntValidator())
        validation.verifyType(self.testcase, 'tests_passed', tests_passed,
                              validation.NoneOk(validation.IntValidator()))
        validation.verifyType(self.testcase, 'tests_failed', tests_failed,
                              validation.NoneOk(validation.IntValidator()))

        yield self.master.db.test_result_sets.completeTestResultSet(test_result_setid,
                                                                    tests_passed, tests_failed)

    # methods from TestResult resource
    @defer.inlineCallbacks
    def addTestResults(self, builderid, test_result_setid, result_values):
        yield self.master.db.test_results.addTestResults(builderid, test_result_setid,
                                                         result_values)


class FakeDataConnector(service.AsyncMultiService):
    # FakeDataConnector delegates to the real DataConnector so it can get all
    # of the proper getter and consumer behavior; it overrides all of the
    # relevant updates with fake methods, though.

    def __init__(self, master, testcase):
        super().__init__()
        self.setServiceParent(master)
        self.updates = FakeUpdates(testcase)
        self.updates.setServiceParent(self)

        # get and control are delegated to a real connector,
        # after some additional assertions
        self.realConnector = connector.DataConnector()
        self.realConnector.setServiceParent(self)
        self.rtypes = self.realConnector.rtypes

    def _scanModule(self, mod):
        return self.realConnector._scanModule(mod)

    def getEndpoint(self, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.getEndpoint(path)

    def getResourceType(self, name):
        return getattr(self.rtypes, name)

    def get(self, path, filters=None, fields=None,
            order=None, limit=None, offset=None):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.get(path, filters=filters, fields=fields,
                                      order=order, limit=limit, offset=offset)

    def control(self, action, args, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.control(action, args, path)
