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
from future.builtins import range

from twisted.internet import defer

from buildbot.schedulers import base
from buildbot.test.fake import fakedb
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

    def setUpScheduler(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantDb=True, wantMq=True, wantData=True)

    def tearDownScheduler(self):
        pass

    def attachScheduler(self, scheduler, objectid, schedulerid,
                        overrideBuildsetMethods=False,
                        createBuilderDB=False):
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

        # set up a fake master
        db = self.db = self.master.db
        self.mq = self.master.mq
        scheduler.setServiceParent(self.master)

        rows = [fakedb.Object(id=objectid, name=scheduler.name,
                              class_name='SomeScheduler'),
                fakedb.Scheduler(id=schedulerid, name=scheduler.name),
                ]
        if createBuilderDB is True:
            rows.extend([fakedb.Builder(name=bname)
                         for bname in scheduler.builderNames])

        db.insertTestData(rows)

        if overrideBuildsetMethods:
            for method in (
                    'addBuildsetForSourceStampsWithDefaults',
                    'addBuildsetForChanges',
                    'addBuildsetForSourceStamps'):
                actual = getattr(scheduler, method)
                fake = getattr(self, 'fake_%s' % method)

                self.assertArgSpecMatches(actual, fake)
                setattr(scheduler, method, fake)
            self.addBuildsetCalls = []
            self._bsidGenerator = iter(range(500, 999))
            self._bridGenerator = iter(range(100, 999))

            # temporarily override the sourcestamp and sourcestampset methods
            self.addedSourceStamps = []
            self.addedSourceStampSets = []

            def fake_addSourceStamp(**kwargs):
                self.assertEqual(kwargs['sourcestampsetid'],
                                 400 + len(self.addedSourceStampSets) - 1)
                self.addedSourceStamps.append(kwargs)
                return defer.succeed(300 + len(self.addedSourceStamps) - 1)
            self.db.sourcestamps.addSourceStamp = fake_addSourceStamp

            def fake_addSourceStampSet():
                self.addedSourceStampSets.append([])
                return defer.succeed(400 + len(self.addedSourceStampSets) - 1)
            self.db.sourcestamps.addSourceStampSet = fake_addSourceStampSet

        # patch methods to detect a failure to upcall the activate and
        # deactivate methods .. unless we're testing BaseScheduler
        def patch(meth):
            oldMethod = getattr(scheduler, meth)

            def newMethod():
                self._parentMethodCalled = False
                d = defer.maybeDeferred(oldMethod)

                @d.addCallback
                def check(rv):
                    self.assertTrue(self._parentMethodCalled,
                                    "'%s' did not call its parent" % meth)
                    return rv
                return d
            setattr(scheduler, meth, newMethod)

            oldParent = getattr(base.BaseScheduler, meth)

            def newParent(self_):
                self._parentMethodCalled = True
                return oldParent(self_)
            self.patch(base.BaseScheduler, meth, newParent)
        if scheduler.__class__.activate != base.BaseScheduler.activate:
            patch('activate')
        if scheduler.__class__.deactivate != base.BaseScheduler.deactivate:
            patch('deactivate')

        self.sched = scheduler
        return scheduler

    @defer.inlineCallbacks
    def setSchedulerToMaster(self, otherMaster):
        sched_id = yield self.master.data.updates.findSchedulerId(self.sched.name)
        if otherMaster:
            self.master.data.updates.schedulerMasters[sched_id] = otherMaster
        else:
            del self.master.data.updates.schedulerMasters[sched_id]

    class FakeChange:
        who = ''
        files = []
        comments = ''
        isdir = 0
        links = None
        revision = None
        when = None
        branch = None
        category = None
        revlink = ''
        properties = {}
        repository = ''
        project = ''
        codebase = ''

    def makeFakeChange(self, **kwargs):
        """Utility method to make a fake Change object with the given
        attributes"""
        ch = self.FakeChange()
        ch.__dict__.update(kwargs)
        return ch

    @defer.inlineCallbacks
    def _addBuildsetReturnValue(self, builderNames):
        if builderNames is None:
            builderNames = self.sched.builderNames
        builderids = []
        builders = yield self.db.builders.getBuilders()
        for builderName in builderNames:
            for bldrDict in builders:
                if builderName == bldrDict["name"]:
                    builderids.append(bldrDict["id"])
                    break

        assert len(builderids) == len(builderNames)
        bsid = next(self._bsidGenerator)
        brids = dict(zip(builderids, self._bridGenerator))
        defer.returnValue((bsid, brids))

    def fake_addBuildsetForSourceStampsWithDefaults(self, reason, sourcestamps=None,
                                                    waited_for=False, properties=None,
                                                    builderNames=None, **kw):
        properties = properties.asDict() if properties is not None else None
        self.assertIsInstance(sourcestamps, list)

        def sourceStampKey(sourceStamp):
            return tuple(sorted(sourceStamp.values()))

        sourcestamps = sorted(sourcestamps, key=sourceStampKey)
        self.addBuildsetCalls.append(('addBuildsetForSourceStampsWithDefaults',
                                      dict(reason=reason, sourcestamps=sourcestamps,
                                           waited_for=waited_for, properties=properties,
                                           builderNames=builderNames)))
        return self._addBuildsetReturnValue(builderNames)

    def fake_addBuildsetForChanges(self, waited_for=False, reason='', external_idstring=None,
                                   changeids=None, builderNames=None, properties=None, **kw):
        if changeids is None:
            changeids = []
        properties = properties.asDict() if properties is not None else None
        self.addBuildsetCalls.append(('addBuildsetForChanges',
                                      dict(waited_for=waited_for, reason=reason,
                                           external_idstring=external_idstring,
                                           changeids=changeids,
                                           properties=properties, builderNames=builderNames,
                                           )))
        return self._addBuildsetReturnValue(builderNames)

    def fake_addBuildsetForSourceStamps(self, waited_for=False, sourcestamps=None,
                                        reason='', external_idstring=None, properties=None,
                                        builderNames=None, **kw):
        if sourcestamps is None:
            sourcestamps = []
        properties = properties.asDict() if properties is not None else None
        self.assertIsInstance(sourcestamps, list)
        sourcestamps.sort()
        self.addBuildsetCalls.append(('addBuildsetForSourceStamps',
                                      dict(reason=reason, external_idstring=external_idstring,
                                           properties=properties, builderNames=builderNames,
                                           sourcestamps=sourcestamps)))

        return self._addBuildsetReturnValue(builderNames)
