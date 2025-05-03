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

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from buildbot.data import connector
from buildbot.data import resultspec
from buildbot.test.util import validation
from buildbot.util import service
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    import datetime


class FakeUpdates(service.AsyncService):
    # unlike "real" update methods, all of the fake methods are here in a
    # single class.

    def __init__(self, testcase, data):
        self.testcase = testcase
        self.data = data

        # test cases should assert the values here:
        self.changesAdded = []  # Changes are numbered starting at 1.

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
                self.testcase.fail(f"value for {k} is not JSON-able")

    # update methods

    def addChange(
        self,
        files=None,
        comments=None,
        author=None,
        committer=None,
        revision=None,
        when_timestamp=None,
        branch=None,
        category=None,
        revlink='',
        properties=None,
        repository='',
        codebase=None,
        project='',
        src=None,
    ):
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
        self.testcase.assertIsInstance(revlink, (type(None), str))
        if properties is not None:
            self.assertProperties(sourced=False, properties=properties)
        self.testcase.assertIsInstance(repository, str)
        self.testcase.assertIsInstance(codebase, (type(None), str))
        self.testcase.assertIsInstance(project, str)
        self.testcase.assertIsInstance(src, (type(None), str))

        self.changesAdded.append({
            'files': files,
            'comments': comments,
            'author': author,
            'committer': committer,
            'revision': revision,
            'when_timestamp': when_timestamp,
            'branch': branch,
            'category': category,
            'revlink': revlink,
            'properties': properties.copy() if properties is not None else None,
            'repository': repository,
            'codebase': codebase,
            'project': project,
            'src': src,
        })
        return self.data.updates.addChange(
            files=files,
            comments=comments,
            author=author,
            committer=committer,
            revision=revision,
            when_timestamp=when_timestamp,
            branch=branch,
            category=category,
            revlink=revlink,
            properties=properties,
            repository=repository,
            codebase=codebase,
            project=project,
            src=src,
        )

    def masterActive(self, name, masterid):
        self.testcase.assertIsInstance(name, str)
        self.testcase.assertIsInstance(masterid, int)
        if masterid:
            self.testcase.assertEqual(masterid, 1)
        return self.data.updates.masterActive(name, masterid)

    def masterStopped(self, name, masterid):
        self.testcase.assertIsInstance(name, str)
        self.testcase.assertEqual(masterid, 1)
        return self.data.updates.masterStopped(name, masterid)

    def expireMasters(self, forceHouseKeeping=False):
        return self.data.updates.expireMasters(forceHouseKeeping=forceHouseKeeping)

    @async_to_deferred
    async def addBuildset(
        self,
        waited_for,
        scheduler=None,
        sourcestamps=None,
        reason='',
        properties=None,
        builderids=None,
        external_idstring=None,
        rebuilt_buildid=None,
        parent_buildid=None,
        parent_relationship=None,
        priority=0,
    ) -> tuple[int, dict[int, int]]:
        self.testcase.assertIsInstance(scheduler, str)
        self.testcase.assertIsInstance(sourcestamps, (type(None), list))
        if sourcestamps is not None:
            for ss in sourcestamps:
                if not isinstance(ss, int) and not isinstance(ss, dict):
                    self.testcase.fail(f"{ss} ({type(ss)}) is not an integer or a dictionary")
        self.testcase.assertIsInstance(reason, str)
        if properties is not None:
            self.assertProperties(sourced=True, properties=properties)
        self.testcase.assertIsInstance(builderids, (type(None), list))
        self.testcase.assertIsInstance(external_idstring, (type(None), str))

        return await self.data.updates.addBuildset(
            waited_for,
            scheduler=scheduler,
            sourcestamps=sourcestamps,
            reason=reason,
            properties=properties,
            builderids=builderids,
            external_idstring=external_idstring,
            rebuilt_buildid=rebuilt_buildid,
            parent_buildid=parent_buildid,
            parent_relationship=parent_relationship,
            priority=priority,
        )

    def maybeBuildsetComplete(self, bsid):
        return self.data.updates.maybeBuildsetComplete(bsid)

    @async_to_deferred
    async def claimBuildRequests(self, brids, claimed_at=None) -> bool:
        validation.verifyType(
            self.testcase, 'brids', brids, validation.ListValidator(validation.IntValidator())
        )
        validation.verifyType(
            self.testcase,
            'claimed_at',
            claimed_at,
            validation.NoneOk(validation.DateTimeValidator()),
        )
        return await self.data.updates.claimBuildRequests(brids, claimed_at=claimed_at)

    @async_to_deferred
    async def unclaimBuildRequests(self, brids) -> None:
        validation.verifyType(
            self.testcase, 'brids', brids, validation.ListValidator(validation.IntValidator())
        )
        return await self.data.updates.unclaimBuildRequests(brids)

    def completeBuildRequests(self, brids, results, complete_at=None):
        validation.verifyType(
            self.testcase, 'brids', brids, validation.ListValidator(validation.IntValidator())
        )
        validation.verifyType(self.testcase, 'results', results, validation.IntValidator())
        validation.verifyType(
            self.testcase,
            'complete_at',
            complete_at,
            validation.NoneOk(validation.DateTimeValidator()),
        )
        return self.data.updates.completeBuildRequests(brids, results, complete_at=complete_at)

    def rebuildBuildrequest(self, buildrequest):
        return self.data.updates.rebuildBuildrequest(buildrequest)

    @async_to_deferred
    async def update_project_info(
        self,
        projectid,
        slug,
        description,
        description_format,
        description_html,
    ) -> None:
        return await self.data.updates.update_project_info(
            projectid, slug, description, description_format, description_html
        )

    def find_project_id(self, name: str, auto_create: bool = True):
        validation.verifyType(self.testcase, 'project name', name, validation.StringValidator())
        validation.verifyType(
            self.testcase, 'auto_create', auto_create, validation.BooleanValidator()
        )
        return self.data.updates.find_project_id(name)

    @async_to_deferred
    async def add_commit(
        self,
        *,
        codebaseid: int,
        author: str,
        committer: str | None = None,
        files: list[str] | None = None,
        comments: str,
        when_timestamp: datetime.datetime,
        revision: str,
        parent_commitid: int | None = None,
    ) -> None:
        validation.verifyType(self.testcase, 'codebaseid', codebaseid, validation.IntValidator())
        validation.verifyType(self.testcase, 'author', author, validation.StringValidator())
        validation.verifyType(
            self.testcase, 'committer', committer, validation.NoneOk(validation.StringValidator())
        )
        validation.verifyType(
            self.testcase,
            'files',
            files,
            validation.NoneOk(validation.StringListValidator()),
        )
        validation.verifyType(self.testcase, 'comments', comments, validation.StringValidator())
        validation.verifyType(
            self.testcase, 'when_timestamp', when_timestamp, validation.IntValidator()
        )
        validation.verifyType(self.testcase, 'revision', revision, validation.StringValidator())
        validation.verifyType(
            self.testcase,
            'parent_commitid',
            parent_commitid,
            validation.NoneOk(validation.IntValidator()),
        )

        return await self.data.updates.add_commit(
            codebaseid=codebaseid,
            author=author,
            committer=committer,
            files=files,
            comments=comments,
            when_timestamp=when_timestamp,
            revision=revision,
            parent_commitid=parent_commitid,
        )

    @async_to_deferred
    async def update_branch(
        self,
        *,
        codebaseid: int,
        name: str,
        commitid: int | None = None,
        last_timestamp: datetime.datetime,
    ) -> None:
        validation.verifyType(self.testcase, 'codebaseid', codebaseid, validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name, validation.StringValidator())
        validation.verifyType(
            self.testcase, 'commitid', commitid, validation.NoneOk(validation.IntValidator())
        )
        validation.verifyType(
            self.testcase, 'last_timestamp', last_timestamp, validation.IntValidator()
        )

        return await self.data.updates.update_branch(
            codebaseid=codebaseid,
            name=name,
            commitid=commitid,
            last_timestamp=last_timestamp,
        )

    @async_to_deferred
    async def update_codebase_info(
        self,
        *,
        codebaseid: int,
        projectid: int,
        slug: str,
    ) -> None:
        validation.verifyType(self.testcase, 'codebaseid', codebaseid, validation.IntValidator())
        validation.verifyType(self.testcase, 'projectid', projectid, validation.IntValidator())
        validation.verifyType(self.testcase, 'slug', slug, validation.StringValidator())

        await self.data.updates.update_codebase_info(
            codebaseid=codebaseid, projectid=projectid, slug=slug
        )

    def find_codebase_id(self, *, projectid: int, name: str, auto_create: bool = True):
        validation.verifyType(self.testcase, 'project id', projectid, validation.IntValidator())
        validation.verifyType(self.testcase, 'codebase name', name, validation.StringValidator())
        return self.data.updates.find_codebase_id(
            projectid=projectid, name=name, auto_create=auto_create
        )

    def updateBuilderList(self, masterid, builderNames):
        self.testcase.assertEqual(masterid, self.master.masterid)
        for n in builderNames:
            self.testcase.assertIsInstance(n, str)
        self.builderNames = builderNames
        return self.data.updates.updateBuilderList(masterid, builderNames)

    @async_to_deferred
    async def updateBuilderInfo(
        self, builderid, description, description_format, description_html, projectid, tags
    ) -> None:
        await self.data.updates.updateBuilderInfo(
            builderid, description, description_format, description_html, projectid, tags
        )

    def findSchedulerId(self, name):
        return self.data.updates.findSchedulerId(name)

    def findChangeSourceId(self, name):
        validation.verifyType(
            self.testcase, 'changesource name', name, validation.StringValidator()
        )
        return self.data.updates.findChangeSourceId(name)

    def findBuilderId(self, name):
        validation.verifyType(self.testcase, 'builder name', name, validation.StringValidator())
        return self.data.updates.findBuilderId(name)

    def trySetSchedulerMaster(self, schedulerid, masterid):
        return self.data.updates.trySetSchedulerMaster(schedulerid, masterid)

    def trySetChangeSourceMaster(self, changesourceid, masterid):
        return self.data.updates.trySetChangeSourceMaster(changesourceid, masterid)

    def addBuild(self, builderid, buildrequestid, workerid):
        validation.verifyType(self.testcase, 'builderid', builderid, validation.IntValidator())
        validation.verifyType(
            self.testcase, 'buildrequestid', buildrequestid, validation.IntValidator()
        )
        validation.verifyType(self.testcase, 'workerid', workerid, validation.IntValidator())
        return self.data.updates.addBuild(builderid, buildrequestid, workerid)

    def generateNewBuildEvent(self, buildid):
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        return self.data.updates.generateNewBuildEvent(buildid)

    def setBuildStateString(self, buildid, state_string):
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(
            self.testcase, 'state_string', state_string, validation.StringValidator()
        )
        return self.data.updates.setBuildStateString(buildid, state_string)

    def add_build_locks_duration(self, buildid, duration_s):
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(self.testcase, 'duration_s', duration_s, validation.IntValidator())
        return self.data.updates.add_build_locks_duration(buildid, duration_s)

    def finishBuild(self, buildid, results):
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(self.testcase, 'results', results, validation.IntValidator())
        return self.data.updates.finishBuild(buildid, results)

    def setBuildProperty(self, buildid, name, value, source):
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name, validation.StringValidator())
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            self.testcase.fail(f"Value for {name} is not JSON-able")
        validation.verifyType(self.testcase, 'source', source, validation.StringValidator())
        return self.data.updates.setBuildProperty(buildid, name, value, source)

    def setBuildProperties(self, buildid, properties) -> None:
        return self.data.updates.setBuildProperties(buildid, properties)

    def addStep(self, buildid, name):
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name, validation.IdentifierValidator(50))
        return self.data.updates.addStep(buildid, name)

    def addStepURL(self, stepid, name, url):
        validation.verifyType(self.testcase, 'stepid', stepid, validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name, validation.StringValidator())
        validation.verifyType(self.testcase, 'url', url, validation.StringValidator())
        return self.data.updates.addStepURL(stepid, name, url)

    def startStep(self, stepid, started_at=None, locks_acquired=False):
        validation.verifyType(self.testcase, 'stepid', stepid, validation.IntValidator())
        validation.verifyType(
            self.testcase, "started_at", started_at, validation.NoneOk(validation.IntValidator())
        )
        validation.verifyType(
            self.testcase, "locks_acquired", locks_acquired, validation.BooleanValidator()
        )
        return self.data.updates.startStep(
            stepid, started_at=started_at, locks_acquired=locks_acquired
        )

    def set_step_locks_acquired_at(self, stepid, locks_acquired_at=None):
        validation.verifyType(self.testcase, 'stepid', stepid, validation.IntValidator())
        validation.verifyType(
            self.testcase,
            "locks_acquired_at",
            locks_acquired_at,
            validation.NoneOk(validation.IntValidator()),
        )
        return self.data.updates.set_step_locks_acquired_at(
            stepid, locks_acquired_at=locks_acquired_at
        )

    def setStepStateString(self, stepid, state_string):
        validation.verifyType(self.testcase, 'stepid', stepid, validation.IntValidator())
        validation.verifyType(
            self.testcase, 'state_string', state_string, validation.StringValidator()
        )
        return self.data.updates.setStepStateString(stepid, state_string)

    def finishStep(self, stepid, results, hidden):
        validation.verifyType(self.testcase, 'stepid', stepid, validation.IntValidator())
        validation.verifyType(self.testcase, 'results', results, validation.IntValidator())
        validation.verifyType(self.testcase, 'hidden', hidden, validation.BooleanValidator())
        return self.data.updates.finishStep(stepid, results, hidden)

    def addLog(self, stepid, name, type):
        validation.verifyType(self.testcase, 'stepid', stepid, validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name, validation.StringValidator())
        validation.verifyType(self.testcase, 'type', type, validation.IdentifierValidator(1))
        return self.data.updates.addLog(stepid, name, type)

    def finishLog(self, logid):
        validation.verifyType(self.testcase, 'logid', logid, validation.IntValidator())
        return self.data.updates.finishLog(logid)

    def compressLog(self, logid):
        validation.verifyType(self.testcase, 'logid', logid, validation.IntValidator())
        return self.data.updates.compressLog(logid)

    def appendLog(self, logid, content):
        validation.verifyType(self.testcase, 'logid', logid, validation.IntValidator())
        validation.verifyType(self.testcase, 'content', content, validation.StringValidator())
        self.testcase.assertEqual(content[-1], '\n')
        return self.data.updates.appendLog(logid, content)

    def findWorkerId(self, name):
        validation.verifyType(
            self.testcase, 'worker name', name, validation.IdentifierValidator(50)
        )
        # this needs to actually get inserted into the db (fake or real) since
        # getWorker will get called later
        return self.data.updates.findWorkerId(name)

    def workerConnected(self, workerid, masterid, workerinfo):
        return self.data.updates.workerConnected(
            workerid=workerid, masterid=masterid, workerinfo=workerinfo
        )

    def workerConfigured(self, workerid, masterid, builderids):
        return self.data.updates.workerConfigured(
            workerid=workerid, masterid=masterid, builderids=builderids
        )

    def workerDisconnected(self, workerid, masterid):
        return self.data.updates.workerDisconnected(workerid=workerid, masterid=masterid)

    def deconfigureAllWorkersForMaster(self, masterid):
        return self.data.updates.deconfigureAllWorkersForMaster(masterid=masterid)

    def workerMissing(self, workerid, masterid, last_connection, notify):
        return self.data.updates.workerMissing(workerid, masterid, last_connection, notify)

    def schedulerEnable(self, schedulerid, v):
        return self.data.updates.schedulerEnable(schedulerid, v)

    def set_worker_paused(self, workerid, paused, pause_reason=None):
        return self.data.updates.set_worker_paused(workerid, paused, pause_reason)

    def set_worker_graceful(self, workerid, graceful):
        return self.data.updates.set_worker_graceful(workerid, graceful)

    # methods form BuildData resource
    @async_to_deferred
    async def setBuildData(self, buildid, name, value, source) -> None:
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(self.testcase, 'name', name, validation.StringValidator())
        validation.verifyType(self.testcase, 'value', value, validation.BinaryValidator())
        validation.verifyType(self.testcase, 'source', source, validation.StringValidator())
        return await self.data.updates.setBuildData(buildid, name, value, source)

    # methods from TestResultSet resource
    @async_to_deferred
    async def addTestResultSet(
        self, builderid, buildid, stepid, description, category, value_unit
    ) -> int:
        validation.verifyType(self.testcase, 'builderid', builderid, validation.IntValidator())
        validation.verifyType(self.testcase, 'buildid', buildid, validation.IntValidator())
        validation.verifyType(self.testcase, 'stepid', stepid, validation.IntValidator())
        validation.verifyType(
            self.testcase, 'description', description, validation.StringValidator()
        )
        validation.verifyType(self.testcase, 'category', category, validation.StringValidator())
        validation.verifyType(self.testcase, 'value_unit', value_unit, validation.StringValidator())
        return await self.data.updates.addTestResultSet(
            builderid, buildid, stepid, description, category, value_unit
        )

    @async_to_deferred
    async def completeTestResultSet(
        self, test_result_setid, tests_passed=None, tests_failed=None
    ) -> None:
        validation.verifyType(
            self.testcase, 'test_result_setid', test_result_setid, validation.IntValidator()
        )
        validation.verifyType(
            self.testcase,
            'tests_passed',
            tests_passed,
            validation.NoneOk(validation.IntValidator()),
        )
        validation.verifyType(
            self.testcase,
            'tests_failed',
            tests_failed,
            validation.NoneOk(validation.IntValidator()),
        )

        await self.data.updates.completeTestResultSet(test_result_setid, tests_passed, tests_failed)

    # methods from TestResult resource
    @async_to_deferred
    async def addTestResults(self, builderid, test_result_setid, result_values) -> None:
        await self.data.updates.addTestResults(builderid, test_result_setid, result_values)


class FakeDataConnector(service.AsyncMultiService):
    # FakeDataConnector delegates to the real DataConnector so it can get all
    # of the proper getter and consumer behavior; it overrides all of the
    # relevant updates with fake methods, though.

    def __init__(self, master, testcase):
        super().__init__()
        self.setServiceParent(master)

        # get, control and updates are delegated to a real connector,
        # after some additional assertions
        self.realConnector = connector.DataConnector()
        self.realConnector.setServiceParent(self)

        self.updates = FakeUpdates(testcase, self.realConnector)
        self.updates.setServiceParent(self)
        self.rtypes = self.realConnector.rtypes

    def _scanModule(self, mod):
        return self.realConnector._scanModule(mod)

    def getEndpoint(self, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.getEndpoint(path)

    def getResourceType(self, name):
        return getattr(self.rtypes, name)

    def get(self, path, filters=None, fields=None, order=None, limit=None, offset=None):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.get(
            path, filters=filters, fields=fields, order=order, limit=limit, offset=offset
        )

    def get_with_resultspec(self, path, rspec):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        if not isinstance(rspec, resultspec.ResultSpec):
            raise TypeError('rspec must be ResultSpec')
        return self.realConnector.get_with_resultspec(path, rspec)

    def control(self, action, args, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.control(action, args, path)

    def resultspec_from_jsonapi(self, args, entityType, is_collection):
        return self.realConnector.resultspec_from_jsonapi(args, entityType, is_collection)
