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

from zope.interface import implements

from buildbot import config
from buildbot import interfaces
from buildbot.process import properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.status import master
from buildbot.steps import trigger
from buildbot.test.fake import fakedb
from buildbot.test.util import steps
from buildbot.test.util.interfaces import InterfaceTests
from mock import Mock
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest


class FakeTriggerable(object):
    implements(interfaces.ITriggerableScheduler)

    triggered_with = None
    result = SUCCESS
    bsid = 1
    brids = {}
    exception = False

    def __init__(self, name):
        self.name = name

    def trigger(self, waited_for, sourcestamps=None, set_props=None,
                parent_buildid=None, parent_relationship=None):
        self.triggered_with = (waited_for, sourcestamps, set_props.properties)
        idsDeferred = defer.Deferred()
        idsDeferred.callback((self.bsid, self.brids))
        resultsDeferred = defer.Deferred()
        if self.exception:
            reactor.callLater(
                0, resultsDeferred.errback, RuntimeError('oh noes'))
        else:
            reactor.callLater(
                0, resultsDeferred.callback, (self.result, self.brids))
        return (idsDeferred, resultsDeferred)


class TriggerableInterfaceTest(unittest.TestCase, InterfaceTests):

    def test_interface(self):
        self.assertInterfacesImplemented(FakeTriggerable)


class FakeSourceStamp(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def asDict(self, includePatch=True):
        return self.__dict__.copy()


class FakeSchedulerManager(object):
    pass

# Magic numbers that relate brid to other build settings
BRID_TO_BSID = lambda brid: brid + 2000
BRID_TO_BID = lambda brid: brid + 3000
BRID_TO_BUILD_NUMBER = lambda brid: brid + 4000


class TestTrigger(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def setupStep(self, step, sourcestampsInBuild=None, gotRevisionsInBuild=None, *args, **kwargs):
        sourcestamps = sourcestampsInBuild or []
        got_revisions = gotRevisionsInBuild or {}

        steps.BuildStepMixin.setupStep(self, step, *args, **kwargs)

        # This step reaches deeply into a number of parts of Buildbot.  That
        # should be fixed!

        # set up a buildmaster that knows about two fake schedulers, a and b
        m = self.master
        m.db.checkForeignKeys = True
        self.build.builder.botmaster = m.botmaster
        m.status = master.Status()
        m.status.setServiceParent(m)
        m.config.buildbotURL = "baseurl/"
        m.scheduler_manager = FakeSchedulerManager()

        self.scheduler_a = a = FakeTriggerable(name='a')
        self.scheduler_b = b = FakeTriggerable(name='b')
        m.scheduler_manager.namedServices = dict(a=a, b=b)

        a.brids = {77: 11}
        b.brids = {78: 22}

        make_fake_br = lambda brid, builderid: fakedb.BuildRequest(
            id=brid, buildsetid=BRID_TO_BSID(brid), builderid=builderid)
        make_fake_build = lambda brid: fakedb.Build(
            buildrequestid=brid, id=BRID_TO_BID(brid),
            number=BRID_TO_BUILD_NUMBER(brid), masterid=9,
            buildslaveid=13)

        m.db.insertTestData([
            fakedb.Builder(id=77, name='A'),
            fakedb.Builder(id=78, name='B'),
            fakedb.Master(id=9),
            fakedb.Buildset(id=2022),
            fakedb.Buildset(id=2011),
            fakedb.Buildslave(id=13, name="some:slave"),
            make_fake_br(11, 77),
            make_fake_br(22, 78),
            make_fake_build(11),
            make_fake_build(22),
        ])

        def getAllSourceStamps():
            return sourcestamps
        self.build.getAllSourceStamps = getAllSourceStamps

        def getAllGotRevisions():
            return got_revisions
        self.step.getAllGotRevisions = getAllGotRevisions

        self.exp_add_sourcestamp = None
        self.exp_a_trigger = None
        self.exp_b_trigger = None
        self.exp_added_urls = []

    def runStep(self):
        d = steps.BuildStepMixin.runStep(self)
        # the build doesn't finish until after a callLater, so this has the
        # effect of checking whether the deferred has been fired already;
        if self.step.waitForFinish:
            self.assertFalse(d.called)
        else:
            self.assertTrue(d.called)

        def check(_):
            self.assertEqual(self.scheduler_a.triggered_with,
                             self.exp_a_trigger)
            self.assertEqual(self.scheduler_b.triggered_with,
                             self.exp_b_trigger)

            # check the URLs
            stepUrls = self.master.data.updates.stepUrls
            if stepUrls:
                got_added_urls = stepUrls[list(stepUrls)[0]]
            else:
                got_added_urls = []
            self.assertEqual(sorted(got_added_urls),
                             sorted(self.exp_added_urls))

            if self.exp_add_sourcestamp:
                self.assertEqual(self.addSourceStamp_kwargs,
                                 self.exp_add_sourcestamp)
        d.addCallback(check)

        # pause runStep's completion until after any other callLater's are done
        def wait(_):
            d = defer.Deferred()
            reactor.callLater(0, d.callback, None)
            return d
        d.addCallback(wait)

        return d

    def expectTriggeredWith(self, a=None, b=None):
        self.exp_a_trigger = a
        if a is not None:
            self.expectTriggeredLinks('a_br')
        self.exp_b_trigger = b
        if b is not None:
            self.expectTriggeredLinks('b_br')

    def expectAddedSourceStamp(self, **kwargs):
        self.exp_add_sourcestamp = kwargs

    def expectTriggeredLinks(self, *args):
        if 'a_br' in args:
            self.exp_added_urls.append(
                ('a #11', 'baseurl/#buildrequests/11'))
        if 'b_br' in args:
            self.exp_added_urls.append(
                ('b #22', 'baseurl/#buildrequests/22'))
        if 'a' in args:
            self.exp_added_urls.append(
                ('success: A #4011', 'baseurl/#builders/77/builds/4011'))
        if 'b' in args:
            self.exp_added_urls.append(
                ('success: B #4022', 'baseurl/#builders/78/builds/4022'))
        if 'afailed' in args:
            self.exp_added_urls.append(
                ('failure: A #4011', 'baseurl/#builders/77/builds/4011'))

    # tests
    def test_no_schedulerNames(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          trigger.Trigger())

    def test_sourceStamp_and_updateSourceStamp(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          trigger.Trigger(schedulerNames=['c'],
                                          sourceStamp=dict(x=1), updateSourceStamp=True))

    def test_sourceStamps_and_updateSourceStamp(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          trigger.Trigger(schedulerNames=['c'],
                                          sourceStamps=[dict(x=1), dict(x=2)],
                                          updateSourceStamp=True))

    def test_updateSourceStamp_and_alwaysUseLatest(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          trigger.Trigger(schedulerNames=['c'],
                                          updateSourceStamp=True, alwaysUseLatest=True))

    def test_sourceStamp_and_alwaysUseLatest(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          trigger.Trigger(schedulerNames=['c'],
                                          sourceStamp=dict(x=1), alwaysUseLatest=True))

    def test_sourceStamps_and_alwaysUseLatest(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          trigger.Trigger(schedulerNames=['c'],
                                          sourceStamps=[dict(x=1), dict(x=2)],
                                          alwaysUseLatest=True))

    def test_simple(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'], sourceStamps={}))
        self.expectOutcome(result=SUCCESS, state_string='triggered a')
        self.expectTriggeredWith(a=(False, [], {}))
        return self.runStep()

    def test_simple_failure(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a']))
        self.scheduler_a.result = FAILURE
        # not waitForFinish, so trigger step succeeds even though the build
        # didn't fail
        self.expectOutcome(result=SUCCESS, state_string='triggered a')
        self.expectTriggeredWith(a=(False, [], {}))
        return self.runStep()

    def test_simple_exception(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a']))
        self.scheduler_a.exception = True
        self.expectOutcome(result=SUCCESS, state_string='triggered a')
        self.expectTriggeredWith(a=(False, [], {}))
        d = self.runStep()

        def flush(_):
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        d.addCallback(flush)
        return d

    @defer.inlineCallbacks
    def test_bogus_scheduler(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a', 'x']))
        # bogus scheduler is an exception, not a failure (dont blame the patch)
        self.expectOutcome(result=EXCEPTION)
        self.expectTriggeredWith(a=None)  # a is not triggered!
        yield self.runStep()
        self.flushLoggedErrors(ValueError)

    def test_updateSourceStamp(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       updateSourceStamp=True),
                       sourcestampsInBuild=[FakeSourceStamp(codebase='',
                                                            repository='x',
                                                            revision=11111)
                                            ],
                       gotRevisionsInBuild={'': 23456},
                       )
        self.expectOutcome(result=SUCCESS, state_string='triggered a')
        self.expectTriggeredWith(
            a=(False, [{'codebase': '', 'repository': 'x', 'revision': 23456}], {}))
        return self.runStep()

    def test_updateSourceStamp_no_got_revision(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       updateSourceStamp=True),
                       sourcestampsInBuild=[FakeSourceStamp(codebase='',
                                                            repository='x',
                                                            revision=11111)
                                            ])
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(
            a=(False,
               # uses old revision
               [{'codebase': '', 'repository': 'x', 'revision': 11111}],
               {}))
        return self.runStep()

    def test_not_updateSourceStamp(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       updateSourceStamp=False),
                       sourcestampsInBuild=[FakeSourceStamp(codebase='',
                                                            repository='x',
                                                            revision=11111)
                                            ],
                       gotRevisionsInBuild={'': 23456},
                       )
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(
            a=(False,
               [{'codebase': '', 'repository': 'x', 'revision': 11111}],
               {}))
        return self.runStep()

    def test_updateSourceStamp_multiple_repositories(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       updateSourceStamp=True),
                       sourcestampsInBuild=[
                           FakeSourceStamp(codebase='cb1',
                                           revision='12345'),
                           FakeSourceStamp(codebase='cb2',
                                           revision='12345')
                           ],
                       gotRevisionsInBuild={'cb1': 23456, 'cb2': 34567},
                       )
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(
            a=(False,
               [{'codebase': 'cb2', 'revision': 34567},
                {'codebase': 'cb1', 'revision': 23456}],
               {}))
        return self.runStep()

    def test_updateSourceStamp_prop_false(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       updateSourceStamp=properties.Property('usess')),
                       sourcestampsInBuild=[FakeSourceStamp(codebase='',
                                                            repository='x',
                                                            revision=11111)
                                            ],
                       gotRevisionsInBuild={'': 23456},
                       )
        self.properties.setProperty('usess', False, 'me')
        self.expectOutcome(result=SUCCESS)
        # didn't use got_revision
        self.expectTriggeredWith(
            a=(False,
                [{'codebase': '', 'repository': 'x', 'revision': 11111}],
                {}))
        return self.runStep()

    def test_updateSourceStamp_prop_true(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       updateSourceStamp=properties.Property('usess')),
                       sourcestampsInBuild=[FakeSourceStamp(codebase='',
                                                            repository='x',
                                                            revision=11111)
                                            ],
                       gotRevisionsInBuild={'': 23456},
                       )
        self.properties.setProperty('usess', True, 'me')
        self.expectOutcome(result=SUCCESS)
        # didn't use got_revision
        self.expectTriggeredWith(
            a=(False,
                [{'codebase': '', 'repository': 'x', 'revision': 23456}],
                {}))
        return self.runStep()

    def test_alwaysUseLatest(self):
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
                                       alwaysUseLatest=True),
                       sourcestampsInBuild=[FakeSourceStamp(codebase='',
                                                            repository='x',
                                                            revision=11111)
                                            ])
        self.expectOutcome(result=SUCCESS)
        # Do not pass setid
        self.expectTriggeredWith(b=(False, [], {}))
        return self.runStep()

    def test_alwaysUseLatest_prop_false(self):
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
                                       alwaysUseLatest=properties.Property('aul')),
                       sourcestampsInBuild=[FakeSourceStamp(codebase='',
                                                            repository='x',
                                                            revision=11111)
                                            ])
        self.properties.setProperty('aul', False, 'me')
        self.expectOutcome(result=SUCCESS)
        # didn't use latest
        self.expectTriggeredWith(
            b=(False, [{'codebase': '', 'repository': 'x', 'revision': 11111}], {}))
        return self.runStep()

    def test_alwaysUseLatest_prop_true(self):
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
                                       alwaysUseLatest=properties.Property('aul')),
                       sourcestampsInBuild=[FakeSourceStamp(codebase='',
                                                            repository='x',
                                                            revision=11111)
                                            ])
        self.properties.setProperty('aul', True, 'me')
        self.expectOutcome(result=SUCCESS)
        # didn't use latest
        self.expectTriggeredWith(b=(False, [], {}))
        return self.runStep()

    def test_sourceStamp(self):
        ss = dict(revision=9876, branch='dev')
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
                                       sourceStamp=ss))
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(b=(False, [ss], {}))
        return self.runStep()

    def test_set_of_sourceStamps(self):
        ss1 = dict(
            codebase='cb1', repository='r1', revision=9876, branch='dev')
        ss2 = dict(
            codebase='cb2', repository='r2', revision=5432, branch='dev')
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
                                       sourceStamps=[ss1, ss2]))
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(b=(False, [ss2, ss1], {}))
        return self.runStep()

    def test_set_of_sourceStamps_override_build(self):
        ss1 = dict(
            codebase='cb1', repository='r1', revision=9876, branch='dev')
        ss2 = dict(
            codebase='cb2', repository='r2', revision=5432, branch='dev')
        ss3 = FakeSourceStamp(
            codebase='cb3', repository='r3', revision=1234, branch='dev')
        ss4 = FakeSourceStamp(
            codebase='cb4', repository='r4', revision=2345, branch='dev')
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
                                       sourceStamps=[ss1, ss2]), sourcestampsInBuild=[ss3, ss4])
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(b=(False, [ss2, ss1], {}))
        return self.runStep()

    def test_sourceStamp_prop(self):
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
                                       sourceStamp=dict(revision=properties.Property('rev'),
                                                        branch='dev')))
        self.properties.setProperty('rev', 602, 'me')
        expected_ss = dict(revision=602, branch='dev')
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(b=(False, [expected_ss], {}))
        return self.runStep()

    def test_waitForFinish(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a', 'b'],
                                       waitForFinish=True))
        self.expectOutcome(result=SUCCESS, state_string='triggered a, b')
        self.expectTriggeredWith(
            a=(True, [], {}),
            b=(True, [], {}))
        self.expectTriggeredLinks('a', 'b')
        return self.runStep()

    def test_waitForFinish_failure(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       waitForFinish=True))
        self.scheduler_a.result = FAILURE
        self.expectOutcome(result=FAILURE)
        self.expectTriggeredWith(a=(True, [], {}))
        self.expectTriggeredLinks('afailed')
        return self.runStep()

    @defer.inlineCallbacks
    def test_waitForFinish_exception(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a', 'b'],
                                       waitForFinish=True))
        self.step.addCompleteLog = Mock()
        self.scheduler_b.exception = True
        self.expectOutcome(result=EXCEPTION,
                           state_string='triggered a, b')
        self.expectTriggeredWith(
            a=(True, [], {}),
            b=(True, [], {}))
        self.expectTriggeredLinks('a')  # b doesn't return a brid
        yield self.runStep()
        self.assertEqual(len(self.step.addCompleteLog.call_args_list), 1)

    def test_set_properties(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       set_properties=dict(x=1, y=2)))
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(a=(False, [],
                                    dict(x=(1, 'Trigger'), y=(2, 'Trigger'))))
        return self.runStep()

    def test_set_properties_prop(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       set_properties=dict(x=properties.Property('X'), y=2)))
        self.properties.setProperty('X', 'xxx', 'here')
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(a=(False, [],
                                    dict(x=('xxx', 'Trigger'), y=(2, 'Trigger'))))
        return self.runStep()

    def test_copy_properties(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       copy_properties=['a', 'b']))
        self.properties.setProperty('a', 'A', 'AA')
        self.properties.setProperty('b', 'B', 'BB')
        self.properties.setProperty('c', 'C', 'CC')
        self.expectOutcome(result=SUCCESS)
        self.expectTriggeredWith(a=(False, [],
                                    dict(a=('A', 'Trigger'),
                                         b=('B', 'Trigger'))))
        return self.runStep()

    def test_waitForFinish_interrupt(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                                       waitForFinish=True))
        self.expectOutcome(result=CANCELLED, state_string='interrupted')
        self.expectTriggeredWith(a=(True, [], {}))
        d = self.runStep()

        # interrupt before the callLater representing the Triggerable
        # schedulers completes
        self.step.interrupt(failure.Failure(RuntimeError('oh noes')))

        return d
