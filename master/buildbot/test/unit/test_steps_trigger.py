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

from twisted.trial import unittest
from twisted.python import failure
from twisted.internet import defer, reactor
from buildbot import config
from buildbot.process import properties
from buildbot.schedulers import triggerable
from buildbot.status import master
from buildbot.status.results import SUCCESS, FAILURE, EXCEPTION
from buildbot.steps import trigger
from buildbot.test.util import steps, compat
from buildbot.test.fake import fakemaster, fakedb

class FakeTriggerable(triggerable.Triggerable):

    triggered_with = None
    result = SUCCESS
    brids = {}
    exception = False

    def trigger(self, sourcestampsetid, set_props=None):
        self.triggered_with = (sourcestampsetid, set_props.properties)
        d = defer.Deferred()
        if self.exception:
            reactor.callLater(0, d.errback, RuntimeError('oh noes'))
        else:
            reactor.callLater(0, d.callback, (self.result, self.brids))
        return d


class FakeSourceStamp(object):

    def __init__(self, _ssid, _setid, **kwargs):
        self._ssid = _ssid
        self._setid = _setid
        self.__dict__.update(kwargs)

    def getAbsoluteSourceStamp(self, rev):
        return FakeSourceStamp(self._ssid + 1000, self._setid + 1000, revision=rev)

    def getSourceStampSetId(self, master):
        return defer.succeed(self._setid)

# Magic numbers that relate brid to other build settings
BRID_TO_BSID = lambda brid: brid+2000
BRID_TO_BID  = lambda brid: brid+3000
BRID_TO_BUILD_NUMBER = lambda brid: brid+4000

class TestTrigger(steps.BuildStepMixin, unittest.TestCase):

    THIS_SSID = 6
    THIS_SS_SETID = 66
    ABS_SS_SETID = THIS_SS_SETID + 1000
    NEW_SSID = 987
    NEW_SS_SETID = 800
    
    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def setupStep(self, *args, **kwargs):
        steps.BuildStepMixin.setupStep(self, *args, **kwargs)

        # This step reaches deeply into a number of parts of Buildbot.  That
        # should be fixed!

        # set up a buildmaster that knows about two fake schedulers, a and b
        self.build.builder.botmaster.parent = m = fakemaster.make_master()
        m.db = fakedb.FakeDBConnector(self)
        m.status = master.Status(m)
        m.config.buildbotURL = "baseurl/"

        self.scheduler_a = a = FakeTriggerable(name='a', builderNames=['A'])
        self.scheduler_b = b = FakeTriggerable(name='b', builderNames=['B'])
        def allSchedulers():
            return [ a, b ]
        m.allSchedulers = allSchedulers

        a.brids = {'A': 11}
        b.brids = {'B': 22}

        make_fake_br = lambda brid, name: fakedb.BuildRequest(id=brid,
                                                              buildsetid=BRID_TO_BSID(brid),
                                                              buildername=name)
        make_fake_build = lambda brid: fakedb.Build(brid=brid,
                                                    id=BRID_TO_BID(brid),
                                                    number=BRID_TO_BUILD_NUMBER(brid))
        
        m.db.insertTestData([
               make_fake_br(11, "A"),
               make_fake_br(22, "B"),
               make_fake_build(11),
               make_fake_build(22),
        ])

        # the build has a getSourceStamp method
        def getSourceStamp():
            return FakeSourceStamp(self.THIS_SSID, self.THIS_SS_SETID)
        self.build.getSourceStamp = getSourceStamp

        # the db has a addSourceStamp method
        def addSourceStamp(**kwargs):
            self.addSourceStamp_kwargs = kwargs
            return defer.succeed(self.NEW_SSID)
        m.db.sourcestamps.addSourceStamp = addSourceStamp

        # the db has a addSourceStampSet method
        def addSourceStampSet():
            return defer.succeed(self.NEW_SS_SETID)
        m.db.sourcestampsets.addSourceStampSet = addSourceStampSet
        
        self.exp_add_sourcestamp = None
        self.exp_a_trigger = None
        self.exp_b_trigger = None
        self.exp_added_urls = []

    def runStep(self, expect_waitForFinish=False):
        d = steps.BuildStepMixin.runStep(self)

        if expect_waitForFinish:
            # the build doesn't finish until after a callLater, so this has the
            # effect of checking whether the deferred has been fired already;
            # it should not have been!
            early = []
            d.addCallback(early.append)
            self.assertEqual(early, [])

        def check(_):
            self.assertEqual(self.scheduler_a.triggered_with,
                             self.exp_a_trigger)
            self.assertEqual(self.scheduler_b.triggered_with,
                             self.exp_b_trigger)
            self.assertEqual(self.step_status.addURL.call_args_list,
                             self.exp_added_urls)

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
        self.exp_b_trigger = b

    def expectAddedSourceStamp(self, **kwargs):
        self.exp_add_sourcestamp = kwargs

    def expectTriggeredLinks(self, *args):
        def get_args(sch, name):
            label = lambda name, num: "%s #%d" % (name, num)
            url = lambda name, num: "baseurl/builders/%s/builds/%d" % (name, num ) 

            num = BRID_TO_BUILD_NUMBER(sch.brids[name])

            #returns the *args and **kwargs that will be called on addURL... 
            #   which is just addURL('label', 'url')
            return ( (label(name,num), url(name,num)) , {} )

        if 'a' in args:
            self.exp_added_urls.append(get_args(self.scheduler_a, 'A'))
        if 'b' in args:
            self.exp_added_urls.append(get_args(self.scheduler_b, 'B'))


    # tests

    def test_no_schedulerNames(self):
        self.assertRaises(config.ConfigErrors, lambda :
                trigger.Trigger())

    def test_sourceStamp_and_updateSourceStamp(self):
        self.assertRaises(config.ConfigErrors, lambda :
                trigger.Trigger(schedulerNames=['c'],
                    sourceStamp=dict(x=1), updateSourceStamp=True))

    def test_updateSourceStamp_and_alwaysUseLatest(self):
        self.assertRaises(config.ConfigErrors, lambda :
                trigger.Trigger(schedulerNames=['c'],
                    updateSourceStamp=True, alwaysUseLatest=True))

    def test_sourceStamp_and_alwaysUseLatest(self):
        self.assertRaises(config.ConfigErrors, lambda :
                trigger.Trigger(schedulerNames=['c'],
                    sourceStamp=dict(x=1), alwaysUseLatest=True))

    def test_simple(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a']))
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID, {}))
        return self.runStep()

    def test_simple_failure(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a']))
        self.scheduler_a.result = FAILURE
        # not waitForFinish, so trigger step succeeds even though the build
        # didn't fail
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID, {}))
        return self.runStep()

    @compat.usesFlushLoggedErrors
    def test_simple_exception(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a']))
        self.scheduler_a.exception = True
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID, {}))
        d = self.runStep()
        def flush(_):
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        d.addCallback(flush)
        return d

    def test_bogus_scheduler(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a', 'x']))
        self.expectOutcome(result=FAILURE, status_text=['no scheduler:', 'x'])
        self.expectTriggeredWith(a=None) # a is not triggered!
        return self.runStep()

    def test_updateSourceStamp(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
            updateSourceStamp=True))
        self.properties.setProperty('got_revision', 23456, 'Source')
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.ABS_SS_SETID, {}))
        return self.runStep()

    def test_updateSourceStamp_no_prop(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
            updateSourceStamp=True))
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID, {}))
        return self.runStep()

    def test_updateSourceStamp_prop(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
            updateSourceStamp=properties.Property('usess')))
        self.properties.setProperty('got_revision', 23456, 'Source')
        self.properties.setProperty('usess', False, 'me')
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        # didn't use SS
        self.expectTriggeredWith(a=(self.THIS_SS_SETID, {}))
        return self.runStep()

    def test_alwaysUseLatest(self):
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
            alwaysUseLatest=True))
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'b'])
        self.expectTriggeredWith(b=(None, {}))
        return self.runStep()

    def test_alwaysUseLatest_prop(self):
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
            alwaysUseLatest=properties.Property('aul')))
        self.properties.setProperty('aul', False, 'me')
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'b'])
        # didn't use latest
        self.expectTriggeredWith(b=(self.THIS_SS_SETID, {}))
        return self.runStep()

    def test_sourceStamp(self):
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
            sourceStamp=dict(revision=9876, branch='dev')))
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'b'])
        self.expectAddedSourceStamp(revision=9876, branch='dev', 
                                    sourcestampsetid=self.NEW_SS_SETID)
        self.expectTriggeredWith(b=(self.NEW_SS_SETID, {}))
        return self.runStep()

    def test_sourceStamp_prop(self):
        self.setupStep(trigger.Trigger(schedulerNames=['b'],
            sourceStamp=dict(revision=properties.Property('rev'),
                branch='dev')))
        self.properties.setProperty('rev', 602, 'me')
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'b'])
        self.expectAddedSourceStamp(revision=602, branch='dev',
                                    sourcestampsetid=self.NEW_SS_SETID)
        self.expectTriggeredWith(b=(self.NEW_SS_SETID, {}))
        return self.runStep()

    def test_waitForFinish(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a', 'b'],
            waitForFinish=True))
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a', 'b'])
        self.expectTriggeredWith(
            a=(self.THIS_SS_SETID, {}),
            b=(self.THIS_SS_SETID, {}))
        self.expectTriggeredLinks('a','b')
        return self.runStep(expect_waitForFinish=True)

    def test_waitForFinish_failure(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
            waitForFinish=True))
        self.scheduler_a.result = FAILURE
        self.expectOutcome(result=FAILURE, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID, {}))
        self.expectTriggeredLinks('a')
        return self.runStep(expect_waitForFinish=True)

    @compat.usesFlushLoggedErrors
    def test_waitForFinish_exception(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a', 'b'],
            waitForFinish=True))
        self.scheduler_b.exception = True
        self.expectOutcome(result=EXCEPTION,
                        status_text=['triggered', 'a', 'b'])
        self.expectTriggeredWith(
            a=(self.THIS_SS_SETID, {}),
            b=(self.THIS_SS_SETID, {}))
        self.expectTriggeredLinks('a') # b doesnt return a brid
        d = self.runStep(expect_waitForFinish=True)
        def flush(_):
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        d.addCallback(flush)
        return d

    def test_set_properties(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                set_properties=dict(x=1, y=2)))
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID,
                                dict(x=(1, 'Trigger'), y=(2, 'Trigger'))))
        return self.runStep()

    def test_set_properties_prop(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                set_properties=dict(x=properties.Property('X'), y=2)))
        self.properties.setProperty('X', 'xxx', 'here')
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID,
                                dict(x=('xxx', 'Trigger'), y=(2, 'Trigger'))))
        return self.runStep()

    def test_copy_properties(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
                copy_properties=['a', 'b']))
        self.properties.setProperty('a', 'A', 'AA')
        self.properties.setProperty('b', 'B', 'BB')
        self.properties.setProperty('c', 'C', 'CC')
        self.expectOutcome(result=SUCCESS, status_text=['triggered', 'a'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID,
                            dict(a=('A', 'AA (in triggering build)'),
                                 b=('B', 'BB (in triggering build)'))))
        return self.runStep()

    def test_interrupt(self):
        self.setupStep(trigger.Trigger(schedulerNames=['a'],
            waitForFinish=True))
        self.expectOutcome(result=EXCEPTION, status_text=['interrupted'])
        self.expectTriggeredWith(a=(self.THIS_SS_SETID, {}))
        d = self.runStep(expect_waitForFinish=True)

        # interrupt before the callLater representing the Triggerable
        # schedulers completes
        self.step.interrupt(failure.Failure(RuntimeError('oh noes')))

        return d
