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
from buildbot.schedulers import base
from buildbot.test.fake import fakemaster, fakedb
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
        pass

    def tearDownScheduler(self):
        pass

    def attachScheduler(self, scheduler, objectid,
            overrideBuildsetMethods=False):
        """Set up a scheduler with a fake master and db; sets self.sched, and
        sets the master's basedir to the absolute path of 'basedir' in the test
        directory.

        If C{overrideBuildsetMethods} is true, then all of the
        addBuildsetForXxx methods are overriden to simply append the method
        name and arguments to self.addBuildsetCalls.  These overriden methods
        return buildsets starting with 500 and buildrequest IDs starting with
        100.

        For C{addBuildsetForSourceStamp}, this also overrides DB API methods
        C{addSourceStamp} and C{addSourceStampSet}, and uses that information
        to generate C{addBuildsetForSourceStamp} results.

        @returns: scheduler
        """
        scheduler.objectid = objectid

        # set up a fake master
        self.master = fakemaster.make_master(testcase=self,
                wantDb=True, wantMq=True, wantData=True)
        db = self.db = self.master.db
        self.mq = self.master.mq
        scheduler.master = self.master

        db.insertTestData([
            fakedb.Object(id=objectid, name=scheduler.name,
                class_name='SomeScheduler'),
        ])

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
            self._bsidGenerator = iter(xrange(500, 999))
            self._bridGenerator = iter(xrange(100, 999))

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
        if scheduler.__class__ != base.BaseScheduler:
            patch('activate')
            patch('deactivate')

        self.sched = scheduler
        return scheduler

    def setSchedulerToMaster(self, otherMaster):
        self.master.data.updates.schedulerIds[self.sched.name] = self.sched.objectid
        if otherMaster:
            self.master.data.updates.schedulerMasters[self.sched.objectid] = otherMaster
        else:
            del self.master.data.updates.schedulerMasters[self.sched.objectid]

    class FakeChange:
        who = ''
        files = []
        comments = ''
        isdir=0
        links=None
        revision=None
        when=None
        branch=None
        category=None
        revlink=''
        properties={}
        repository=''
        project=''
        codebase=''

    def makeFakeChange(self, **kwargs):
        """Utility method to make a fake Change object with the given
        attributes"""
        ch = self.FakeChange()
        ch.__dict__.update(kwargs)
        return ch

    def _addBuildsetReturnValue(self, builderNames):
        if builderNames is None:
            builderNames = self.sched.builderNames
        bsid = self._bsidGenerator.next()
        brids = dict(zip(builderNames, self._bridGenerator))
        return defer.succeed((bsid, brids))

    def fake_addBuildsetForSourceStampsWithDefaults(self, reason, sourcestamps,
            properties=None, builderNames=None):
        properties = properties.asDict()
        self.assertIsInstance(sourcestamps, list)
        sourcestamps.sort()
        self.addBuildsetCalls.append(('addBuildsetForSourceStampsWithDefaults',
                                            locals()))
        self.addBuildsetCalls[-1][1].pop('self')
        return self._addBuildsetReturnValue(builderNames)

    def fake_addBuildsetForChanges(self, reason='', external_idstring=None,
            changeids=[], builderNames=None, properties=None):
        properties = properties.asDict() if properties is not None else None
        self.addBuildsetCalls.append(('addBuildsetForChanges', locals()))
        self.addBuildsetCalls[-1][1].pop('self')
        return self._addBuildsetReturnValue(builderNames)

    def fake_addBuildsetForSourceStamps(self, sourcestamps=[], reason='',
            external_idstring=None, properties=None, builderNames=None):
        properties=properties.asDict() if properties is not None else None
        self.assertIsInstance(sourcestamps, list)
        sourcestamps.sort()
        self.addBuildsetCalls.append(('addBuildsetForSourceStamp',
            dict(reason=reason, external_idstring=external_idstring,
                properties=properties, builderNames=builderNames,
                sourcestamps=sourcestamps)))

        return self._addBuildsetReturnValue(builderNames)
