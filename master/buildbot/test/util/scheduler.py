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

from twisted.internet import defer

from buildbot.process.properties import Properties
from buildbot.schedulers import base
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import interfaces


class SchedulerMixin(interfaces.InterfaceTests):
    """
    This class fakes out enough of a master and the various relevant database
    connectors to test schedulers.  All of the database methods have identical
    signatures to the real database connectors, but for ease of testing always
    return an already-fired Deferred, meaning that there is no need to wait for
    events to complete.

    This class is tightly coupled with the various L{buildbot.test.fake.fakedb}
    module.  All instance variables are only available after C{attachScheduler}
    has been called.

    @ivar sched: scheduler instance
    @ivar master: the fake master
    @ivar db: the fake db (same as C{self.master.db}, but shorter)
    """

    OTHER_MASTER_ID = 93

    @defer.inlineCallbacks
    def setUpScheduler(self):
        self.master = yield fakemaster.make_master(self, wantDb=True, wantMq=True, wantData=True)

    @defer.inlineCallbacks
    def attachScheduler(
        self, scheduler, objectid, schedulerid, overrideBuildsetMethods=False, createBuilderDB=False
    ):
        """Set up a scheduler with a fake master and db; sets self.sched, and
        sets the master's basedir to the absolute path of 'basedir' in the test
        directory.

        If C{overrideBuildsetMethods} is true, then all of the
        addBuildsetForXxx methods are overridden to simply append the method
        name and arguments to self.addBuildsetCalls.  These overridden methods
        return buildsets starting with 500 and buildrequest IDs starting with
        100.

        For C{addBuildsetForSourceStamp}, this also overrides DB API methods
        C{addSourceStamp} and C{addSourceStampSet}, and uses that information
        to generate C{addBuildsetForSourceStamp} results.

        @returns: scheduler
        """
        scheduler.objectid = objectid

        rows = [
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Master(id=self.OTHER_MASTER_ID),
            fakedb.Scheduler(id=schedulerid, name=scheduler.name),
        ]
        if createBuilderDB is True:
            rows.extend([
                fakedb.Builder(id=300 + i, name=bname)
                for i, bname in enumerate(scheduler.builderNames)
            ])

        yield self.master.db.insert_test_data(rows)

        yield scheduler.setServiceParent(self.master)

        if overrideBuildsetMethods:
            self.assertArgSpecMatches(
                scheduler.addBuildsetForSourceStampsWithDefaults,
                self.fake_addBuildsetForSourceStampsWithDefaults,
            )
            scheduler.addBuildsetForSourceStampsWithDefaults = (
                self.fake_addBuildsetForSourceStampsWithDefaults
            )

            self.assertArgSpecMatches(
                scheduler.addBuildsetForChanges, self.fake_addBuildsetForChanges
            )
            scheduler.addBuildsetForChanges = self.fake_addBuildsetForChanges

            self.assertArgSpecMatches(
                scheduler.addBuildsetForSourceStamps, self.fake_addBuildsetForSourceStamps
            )
            scheduler.addBuildsetForSourceStamps = self.fake_addBuildsetForSourceStamps

            self.addBuildsetCalls = []
            self._bsidGenerator = iter(range(500, 999))
            self._bridGenerator = iter(range(100, 999))

            # temporarily override the sourcestamp and sourcestampset methods
            self.addedSourceStamps = []
            self.addedSourceStampSets = []

            def fake_addSourceStamp(**kwargs):
                self.assertEqual(
                    kwargs['sourcestampsetid'], 400 + len(self.addedSourceStampSets) - 1
                )
                self.addedSourceStamps.append(kwargs)
                return defer.succeed(300 + len(self.addedSourceStamps) - 1)

            self.master.db.sourcestamps.addSourceStamp = fake_addSourceStamp

            def fake_addSourceStampSet():
                self.addedSourceStampSets.append([])
                return defer.succeed(400 + len(self.addedSourceStampSets) - 1)

            self.master.db.sourcestamps.addSourceStampSet = fake_addSourceStampSet

        # patch methods to detect a failure to upcall the activate and
        # deactivate methods .. unless we're testing BaseScheduler
        def patch(scheduler_class, meth):
            oldMethod = getattr(scheduler, meth)

            @defer.inlineCallbacks
            def newMethod():
                self._parentMethodCalled = False
                rv = yield oldMethod()

                self.assertTrue(self._parentMethodCalled, f"'{meth}' did not call its parent")
                return rv

            setattr(scheduler, meth, newMethod)

            oldParent = getattr(scheduler_class, meth)

            def newParent(self_):
                self._parentMethodCalled = True
                return oldParent(self_)

            self.patch(base.BaseScheduler, meth, newParent)
            self.patch(base.ReconfigurableBaseScheduler, meth, newParent)

        if (
            isinstance(scheduler, base.BaseScheduler)
            and scheduler.__class__.activate != base.BaseScheduler.activate
        ):
            patch(base.BaseScheduler, 'activate')
        if (
            isinstance(scheduler, base.BaseScheduler)
            and scheduler.__class__.deactivate != base.BaseScheduler.deactivate
        ):
            patch(base.BaseScheduler, 'deactivate')
        if (
            isinstance(scheduler, base.ReconfigurableBaseScheduler)
            and scheduler.__class__.activate != base.ReconfigurableBaseScheduler.activate
        ):
            patch(base.ReconfigurableBaseScheduler, 'activate')
        if (
            isinstance(scheduler, base.ReconfigurableBaseScheduler)
            and scheduler.__class__.deactivate != base.ReconfigurableBaseScheduler.deactivate
        ):
            patch(base.ReconfigurableBaseScheduler, 'deactivate')

        self.sched = scheduler
        return scheduler

    @defer.inlineCallbacks
    def setSchedulerToMaster(self, otherMaster):
        sched_id = yield self.master.data.updates.findSchedulerId(self.sched.name)
        yield self.master.data.updates.trySetSchedulerMaster(sched_id, otherMaster)

    class FakeChange:
        who = ''
        files: list[str] = []
        comments = ''
        isdir = 0
        links = None
        revision = None
        when = None
        branch = None
        category = None
        number = None
        revlink = ''
        properties: dict[str, str] = {}
        repository = ''
        project = ''
        codebase = ''

    def makeFakeChange(self, **kwargs):
        """Utility method to make a fake Change object with the given
        attributes"""
        ch = self.FakeChange()
        ch.__dict__.update(kwargs)
        properties = ch.properties
        ch.properties = Properties()
        ch.properties.update(properties, "Change")
        return ch

    @defer.inlineCallbacks
    def addFakeChange(self, change):
        old_change_number = change.number
        change.number = yield self.master.db.changes.addChange(
            author=change.who,
            files=change.files,
            comments=change.comments,
            revision=change.revision,
            when_timestamp=change.when,
            branch=change.branch,
            category=change.category,
            revlink=change.revlink,
            properties=change.properties.asDict(),
            repository=change.repository,
            codebase=change.codebase,
            project=change.project,
            _test_changeid=change.number,
        )
        if old_change_number is not None:
            self.assertEqual(change.number, old_change_number)
        return change

    @defer.inlineCallbacks
    def _addBuildsetReturnValue(self, builderNames):
        if builderNames is None:
            builderNames = self.sched.builderNames
        builderids = []
        builders = yield self.master.db.builders.getBuilders()
        for builderName in builderNames:
            for bldrDict in builders:
                if builderName == bldrDict.name:
                    builderids.append(bldrDict.id)
                    break

        assert len(builderids) == len(builderNames)
        bsid = next(self._bsidGenerator)
        brids = dict(zip(builderids, self._bridGenerator))
        return (bsid, brids)

    @defer.inlineCallbacks
    def assert_classifications(self, schedulerid, expected_classifications):
        classifications = yield self.master.db.schedulers.getChangeClassifications(schedulerid)
        self.assertEqual(classifications, expected_classifications)

    def fake_addBuildsetForSourceStampsWithDefaults(
        self,
        reason,
        sourcestamps=None,
        waited_for=False,
        properties=None,
        builderNames=None,
        priority=None,
        **kw,
    ):
        properties = properties.asDict() if properties is not None else None
        self.assertIsInstance(sourcestamps, list)

        def sourceStampKey(sourceStamp):
            return sourceStamp.get("codebase")

        sourcestamps = sorted(sourcestamps, key=sourceStampKey)
        self.addBuildsetCalls.append((
            'addBuildsetForSourceStampsWithDefaults',
            {
                "reason": reason,
                "sourcestamps": sourcestamps,
                "waited_for": waited_for,
                "properties": properties,
                "builderNames": builderNames,
                "priority": priority,
            },
        ))
        return self._addBuildsetReturnValue(builderNames)

    def fake_addBuildsetForChanges(
        self,
        waited_for=False,
        reason='',
        external_idstring=None,
        changeids=None,
        builderNames=None,
        properties=None,
        priority=None,
        **kw,
    ):
        if changeids is None:
            changeids = []
        properties = properties.asDict() if properties is not None else None
        self.addBuildsetCalls.append((
            'addBuildsetForChanges',
            {
                "waited_for": waited_for,
                "reason": reason,
                "external_idstring": external_idstring,
                "changeids": changeids,
                "properties": properties,
                "builderNames": builderNames,
                "priority": priority,
            },
        ))
        return self._addBuildsetReturnValue(builderNames)

    def fake_addBuildsetForSourceStamps(
        self,
        waited_for=False,
        sourcestamps=None,
        reason='',
        external_idstring=None,
        properties=None,
        builderNames=None,
        priority=None,
        **kw,
    ):
        if sourcestamps is None:
            sourcestamps = []
        properties = properties.asDict() if properties is not None else None
        self.assertIsInstance(sourcestamps, list)
        sourcestamps.sort()
        self.addBuildsetCalls.append((
            'addBuildsetForSourceStamps',
            {
                "reason": reason,
                "external_idstring": external_idstring,
                "properties": properties,
                "builderNames": builderNames,
                "sourcestamps": sourcestamps,
            },
        ))

        return self._addBuildsetReturnValue(builderNames)
