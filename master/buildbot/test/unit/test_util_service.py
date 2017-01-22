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
from future.utils import text_type

import mock

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot import config
from buildbot.util import service


class DeferredStartStop(service.AsyncService):

    def startService(self):
        self.d = defer.Deferred()
        return self.d

    def stopService(self):
        self.d = defer.Deferred()
        return self.d


class AsyncMultiService(unittest.TestCase):

    def setUp(self):
        self.svc = service.AsyncMultiService()

    @defer.inlineCallbacks
    def test_empty(self):
        yield self.svc.startService()
        yield self.svc.stopService()

    def test_waits_for_child_services(self):
        child = DeferredStartStop()
        child.setServiceParent(self.svc)

        d = self.svc.startService()
        self.assertFalse(d.called)
        child.d.callback(None)
        self.assertTrue(d.called)

        d = self.svc.stopService()
        self.assertFalse(d.called)
        child.d.callback(None)
        self.assertTrue(d.called)

    def test_child_fails(self):
        child = DeferredStartStop()
        child.setServiceParent(self.svc)

        d = self.svc.startService()
        self.assertFalse(d.called)
        child.d.errback(RuntimeError('oh noes'))
        self.assertTrue(d.called)

        @d.addErrback
        def check(f):
            f.check(RuntimeError)

        d = self.svc.stopService()
        self.assertFalse(d.called)
        child.d.errback(RuntimeError('oh noes'))
        self.assertTrue(d.called)

        @d.addErrback
        def check_again(f):
            f.check(RuntimeError)

    def test_child_starts_on_sSP(self):
        d = self.svc.startService()
        self.assertTrue(d.called)

        child = DeferredStartStop()
        d = child.setServiceParent(self.svc)
        self.assertFalse(d.called)
        child.d.callback(None)
        self.assertTrue(d.called)


class ClusteredBuildbotService(unittest.TestCase):
    SVC_NAME = 'myName'
    SVC_ID = 20

    class DummyService(service.ClusteredBuildbotService):
        pass

    def setUp(self):
        self.svc = self.makeService()

    def tearDown(self):
        pass

    def makeService(self, name=SVC_NAME, serviceid=SVC_ID):
        svc = self.DummyService(name=name)

        svc.clock = task.Clock()

        self.setServiceClaimable(svc, defer.succeed(False))
        self.setActivateToReturn(svc, defer.succeed(None))
        self.setDeactivateToReturn(svc, defer.succeed(None))
        self.setGetServiceIdToReturn(svc, defer.succeed(serviceid))
        self.setUnclaimToReturn(svc, defer.succeed(None))

        return svc

    def makeMock(self, value):
        mockObj = mock.Mock()
        if isinstance(value, Exception):
            mockObj.side_effect = value
        else:
            mockObj.return_value = value
        return mockObj

    def setServiceClaimable(self, svc, claimable):
        svc._claimService = self.makeMock(claimable)

    def setGetServiceIdToReturn(self, svc, serviceid):
        svc._getServiceId = self.makeMock(serviceid)

    def setUnclaimToReturn(self, svc, unclaim):
        svc._unclaimService = self.makeMock(unclaim)

    def setActivateToReturn(self, svc, activate):
        svc.activate = self.makeMock(activate)

    def setDeactivateToReturn(self, svc, deactivate):
        svc.deactivate = self.makeMock(deactivate)

    def test_name_PreservesUnicodePromotion(self):
        svc = self.makeService(name=u'n')

        self.assertIsInstance(svc.name, text_type)
        self.assertEqual(svc.name, u'n')

    def test_name_GetsUnicodePromotion(self):
        svc = self.makeService(name='n')

        self.assertIsInstance(svc.name, text_type)
        self.assertEqual(svc.name, u'n')

    def test_compare(self):
        a = self.makeService(name='a', serviceid=20)
        b1 = self.makeService(name='b', serviceid=21)
        b2 = self.makeService(name='b', serviceid=21)  # same args as 'b1'
        b3 = self.makeService(name='b', serviceid=20)  # same id as 'a'

        self.assertTrue(a == a)
        self.assertTrue(a != b1)
        self.assertTrue(a != b2)
        self.assertTrue(a != b3)

        self.assertTrue(b1 != a)
        self.assertTrue(b1 == b1)
        self.assertTrue(b1 == b2)
        self.assertTrue(b1 == b3)

    def test_create_NothingCalled(self):
        # None of the member functions get called until startService happens
        self.assertFalse(self.svc.activate.called)
        self.assertFalse(self.svc.deactivate.called)
        self.assertFalse(self.svc._getServiceId.called)
        self.assertFalse(self.svc._claimService.called)
        self.assertFalse(self.svc._unclaimService.called)

    def test_create_IsInactive(self):
        # starts in inactive state
        self.assertFalse(self.svc.isActive())

    def test_create_HasNoServiceIdYet(self):
        # has no service id at first
        self.assertIdentical(self.svc.serviceid, None)

    def test_start_UnclaimableSoNotActiveYet(self):
        self.svc.startService()

        self.assertFalse(self.svc.isActive())

    def test_start_GetsServiceIdAssigned(self):
        self.svc.startService()

        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)

        self.assertEqual(self.SVC_ID, self.svc.serviceid)

    def test_start_WontPollYet(self):
        self.svc.startService()

        # right before the poll interval, nothing has tried again yet
        self.svc.clock.advance(self.svc.POLL_INTERVAL_SEC * 0.95)

        self.assertEqual(0, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)

        self.assertEqual(0, self.svc.deactivate.call_count)
        self.assertEqual(0, self.svc._unclaimService.call_count)

        self.assertFalse(self.svc.isActive())

    @defer.inlineCallbacks
    def test_start_PollButClaimFails(self):
        yield self.svc.startService()

        # at the POLL time, it gets called again, but we're still inactive...
        self.svc.clock.advance(self.svc.POLL_INTERVAL_SEC * 1.05)

        self.assertEqual(0, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(2, self.svc._claimService.call_count)

        self.assertEqual(0, self.svc.deactivate.call_count)
        self.assertEqual(0, self.svc._unclaimService.call_count)

        self.assertEqual(False, self.svc.isActive())

    def test_start_PollsPeriodically(self):
        NUMBER_OF_POLLS = 15

        self.svc.startService()

        for i in range(NUMBER_OF_POLLS):
            self.svc.clock.advance(self.svc.POLL_INTERVAL_SEC)

        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(
            1 + NUMBER_OF_POLLS, self.svc._claimService.call_count)

    def test_start_ClaimSucceeds(self):
        self.setServiceClaimable(self.svc, defer.succeed(True))

        self.svc.startService()

        self.assertEqual(1, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)

        self.assertEqual(0, self.svc.deactivate.call_count)
        self.assertEqual(0, self.svc._unclaimService.call_count)

        self.assertEqual(True, self.svc.isActive())

    def test_start_PollingAfterClaimSucceedsDoesNothing(self):
        self.setServiceClaimable(self.svc, defer.succeed(True))

        self.svc.startService()

        # another epoch shouldn't do anything further...
        self.svc.clock.advance(self.svc.POLL_INTERVAL_SEC * 2)

        self.assertEqual(1, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)

        self.assertEqual(0, self.svc.deactivate.call_count)
        self.assertEqual(0, self.svc._unclaimService.call_count)

        self.assertEqual(True, self.svc.isActive())

    def test_stopWhileStarting_NeverActive(self):
        self.svc.startService()
        #   .. claim fails

        stopDeferred = self.svc.stopService()

        # a stop at this point unwinds things immediately
        self.successResultOf(stopDeferred)

        # advance the clock, and nothing should happen
        self.svc.clock.advance(self.svc.POLL_INTERVAL_SEC * 2)

        self.assertEqual(1, self.svc._claimService.call_count)
        self.assertEqual(0, self.svc._unclaimService.call_count)
        self.assertEqual(0, self.svc.deactivate.call_count)

        self.assertFalse(self.svc.isActive())

    def test_stop_AfterActivated(self):
        self.setServiceClaimable(self.svc, defer.succeed(True))
        self.svc.startService()

        # now deactivate:
        stopDeferred = self.svc.stopService()

        # immediately stops
        self.successResultOf(stopDeferred)

        self.assertEqual(1, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)

        self.assertEqual(1, self.svc._unclaimService.call_count)
        self.assertEqual(1, self.svc.deactivate.call_count)

        self.assertEqual(False, self.svc.isActive())

    def test_stop_AfterActivated_NoDeferred(self):
        # set all the child-class functions to return non-deferreds,
        # just to check we can handle both:
        self.setServiceClaimable(self.svc, True)
        self.setActivateToReturn(self.svc, None)
        self.setDeactivateToReturn(self.svc, None)
        self.setGetServiceIdToReturn(self.svc, self.SVC_ID)
        self.setUnclaimToReturn(self.svc, None)

        self.svc.startService()

        # now deactivate:
        stopDeferred = self.svc.stopService()

        # immediately stops
        self.successResultOf(stopDeferred)

        self.assertEqual(1, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)

        self.assertEqual(1, self.svc._unclaimService.call_count)
        self.assertEqual(1, self.svc.deactivate.call_count)

        self.assertEqual(False, self.svc.isActive())

    def test_stopWhileStarting_getServiceIdTakesForever(self):
        # create a deferred that will take a while...
        svcIdDeferred = defer.Deferred()
        self.setGetServiceIdToReturn(self.svc, svcIdDeferred)

        self.setServiceClaimable(self.svc, defer.succeed(True))
        self.svc.startService()

        # stop before it has the service id (the svcIdDeferred is stuck)
        stopDeferred = self.svc.stopService()

        self.assertNoResult(stopDeferred)

        # .. no deactivates yet....
        self.assertEqual(0, self.svc.deactivate.call_count)
        self.assertEqual(0, self.svc.activate.call_count)
        self.assertEqual(0, self.svc._claimService.call_count)
        self.assertEqual(False, self.svc.isActive())

        # then let service id part finish
        svcIdDeferred.callback(None)

        # ... which will cause the stop to also finish
        self.successResultOf(stopDeferred)

        # and everything else should unwind too:
        self.assertEqual(1, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)

        self.assertEqual(1, self.svc.deactivate.call_count)
        self.assertEqual(1, self.svc._unclaimService.call_count)

        self.assertEqual(False, self.svc.isActive())

    def test_stopWhileStarting_claimServiceTakesForever(self):
        # create a deferred that will take a while...
        claimDeferred = defer.Deferred()
        self.setServiceClaimable(self.svc, claimDeferred)

        self.svc.startService()
        #   .. claim is still pending here

        # stop before it's done activating
        stopDeferred = self.svc.stopService()

        self.assertNoResult(stopDeferred)

        # .. no deactivates yet....
        self.assertEqual(0, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)
        self.assertEqual(0, self.svc.deactivate.call_count)
        self.assertEqual(0, self.svc._unclaimService.call_count)
        self.assertEqual(False, self.svc.isActive())

        # then let claim succeed, but we should see things unwind
        claimDeferred.callback(True)

        # ... which will cause the stop to also finish
        self.successResultOf(stopDeferred)

        # and everything else should unwind too:
        self.assertEqual(1, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)
        self.assertEqual(1, self.svc.deactivate.call_count)
        self.assertEqual(1, self.svc._unclaimService.call_count)
        self.assertEqual(False, self.svc.isActive())

    def test_stopWhileStarting_activateTakesForever(self):
        """If activate takes forever, things acquiesce nicely"""
        # create a deferreds that will take a while...
        activateDeferred = defer.Deferred()
        self.setActivateToReturn(self.svc, activateDeferred)

        self.setServiceClaimable(self.svc, defer.succeed(True))
        self.svc.startService()

        # stop before it's done activating
        stopDeferred = self.svc.stopService()

        self.assertNoResult(stopDeferred)

        # .. no deactivates yet....
        self.assertEqual(1, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)
        self.assertEqual(0, self.svc.deactivate.call_count)
        self.assertEqual(0, self.svc._unclaimService.call_count)
        self.assertEqual(True, self.svc.isActive())

        # then let activate finish
        activateDeferred.callback(None)

        # ... which will cause the stop to also finish
        self.successResultOf(stopDeferred)

        # and everything else should unwind too:
        self.assertEqual(1, self.svc.activate.call_count)
        self.assertEqual(1, self.svc._getServiceId.call_count)
        self.assertEqual(1, self.svc._claimService.call_count)
        self.assertEqual(1, self.svc.deactivate.call_count)
        self.assertEqual(1, self.svc._unclaimService.call_count)
        self.assertEqual(False, self.svc.isActive())

    def test_stop_unclaimTakesForever(self):
        # create a deferred that will take a while...
        unclaimDeferred = defer.Deferred()
        self.setUnclaimToReturn(self.svc, unclaimDeferred)

        self.setServiceClaimable(self.svc, defer.succeed(True))
        self.svc.startService()

        # stop before it's done activating
        stopDeferred = self.svc.stopService()

        self.assertNoResult(stopDeferred)

        # .. no deactivates yet....
        self.assertEqual(1, self.svc.deactivate.call_count)
        self.assertEqual(1, self.svc._unclaimService.call_count)
        self.assertEqual(False, self.svc.isActive())

        # then let unclaim part finish
        unclaimDeferred.callback(None)
        # ... which will cause the stop to finish
        self.successResultOf(stopDeferred)

        # and everything should unwind:
        self.assertEqual(1, self.svc.deactivate.call_count)
        self.assertEqual(1, self.svc._unclaimService.call_count)
        self.assertEqual(False, self.svc.isActive())

    def test_stop_deactivateTakesForever(self):
        # create a deferred that will take a while...
        deactivateDeferred = defer.Deferred()
        self.setDeactivateToReturn(self.svc, deactivateDeferred)

        self.setServiceClaimable(self.svc, defer.succeed(True))
        self.svc.startService()

        # stop before it's done activating
        stopDeferred = self.svc.stopService()

        self.assertNoResult(stopDeferred)

        self.assertEqual(1, self.svc.deactivate.call_count)
        self.assertEqual(0, self.svc._unclaimService.call_count)
        self.assertEqual(False, self.svc.isActive())

        # then let deactivate finish
        deactivateDeferred.callback(None)
        # ... which will cause the stop to finish
        self.successResultOf(stopDeferred)

        # and everything else should unwind too:
        self.assertEqual(1, self.svc.deactivate.call_count)
        self.assertEqual(1, self.svc._unclaimService.call_count)
        self.assertEqual(False, self.svc.isActive())

    def test_claim_raises(self):
        self.setServiceClaimable(self.svc, RuntimeError())

        self.svc.startService()

        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        self.assertEqual(False, self.svc.isActive())

    @defer.inlineCallbacks
    def test_activate_raises(self):
        self.setServiceClaimable(self.svc, defer.succeed(True))
        self.setActivateToReturn(self.svc, RuntimeError())

        yield self.svc.startService()

        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        # half-active: we actually return True in this case:
        self.assertEqual(True, self.svc.isActive())

    def test_deactivate_raises(self):
        self.setServiceClaimable(self.svc, defer.succeed(True))
        self.setDeactivateToReturn(self.svc, RuntimeError())

        self.svc.startService()
        self.svc.stopService()

        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        self.assertEqual(False, self.svc.isActive())

    def test_unclaim_raises(self):
        self.setServiceClaimable(self.svc, defer.succeed(True))
        self.setUnclaimToReturn(self.svc, RuntimeError())

        self.svc.startService()
        self.svc.stopService()

        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        self.assertEqual(False, self.svc.isActive())


class MyService(service.BuildbotService):

    def checkConfig(self, foo, a=None):
        if a is None:
            config.error("a must be specified")
        return defer.succeed(True)

    def reconfigService(self, *argv, **kwargs):
        self.config = argv, kwargs
        return defer.succeed(None)


class fakeConfig(object):
    pass


class fakeMaster(service.MasterService, service.ReconfigurableServiceMixin):
    pass


def makeFakeMaster():
    m = fakeMaster()
    m.db = mock.Mock()
    return m


class BuildbotService(unittest.TestCase):

    def setUp(self):
        self.master = makeFakeMaster()

    @defer.inlineCallbacks
    def prepareService(self):
        self.master.config = fakeConfig()
        serv = MyService(1, a=2, name="basic")
        yield serv.setServiceParent(self.master)
        yield self.master.startService()
        yield serv.reconfigServiceWithSibling(serv)
        defer.returnValue(serv)

    @defer.inlineCallbacks
    def testNominal(self):
        yield self.prepareService()
        self.assertEqual(
            self.master.namedServices["basic"].config, ((1,), dict(a=2)))

    @defer.inlineCallbacks
    def testConfigDict(self):
        serv = yield self.prepareService()
        self.assertEqual(serv.getConfigDict(), {
            'args': (1,),
            'class': 'buildbot.test.unit.test_util_service.MyService',
            'kwargs': {'a': 2},
            'name': 'basic'})

    def testNoName(self):
        self.assertRaises(ValueError, lambda: MyService(1, a=2))

    def testChecksDone(self):
        self.assertRaises(
            config.ConfigErrors, lambda: MyService(1, name="foo"))


class BuildbotServiceManager(unittest.TestCase):

    def setUp(self):
        self.master = makeFakeMaster()

    @defer.inlineCallbacks
    def prepareService(self):
        self.master.config = fakeConfig()
        serv = MyService(1, a=2, name="basic")
        self.master.config.services = {"basic": serv}
        self.manager = service.BuildbotServiceManager()
        yield self.manager.setServiceParent(self.master)
        yield self.master.startService()
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)
        defer.returnValue(serv)

    @defer.inlineCallbacks
    def testNominal(self):
        yield self.prepareService()
        self.assertEqual(
            self.manager.namedServices["basic"].config, ((1,), dict(a=2)))

    @defer.inlineCallbacks
    def testReconfigNoChange(self):
        serv = yield self.prepareService()
        serv.config = None  # 'de-configure' the service
        # reconfigure with the same config
        serv2 = MyService(1, a=2, name="basic")
        self.master.config.services = {"basic": serv2}

        # reconfigure the master
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)
        # the first service is still used
        self.assertIdentical(self.manager.namedServices["basic"], serv)
        # the second service is not used
        self.assertNotIdentical(self.manager.namedServices["basic"], serv2)

        # reconfigServiceWithConstructorArgs was not called
        self.assertEqual(serv.config, None)

    @defer.inlineCallbacks
    def testReconfigWithChanges(self):
        serv = yield self.prepareService()
        serv.config = None  # 'de-configure' the service

        # reconfigure with the different config
        serv2 = MyService(1, a=4, name="basic")
        self.master.config.services = {"basic": serv2}

        # reconfigure the master
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)
        # the first service is still used
        self.assertIdentical(self.manager.namedServices["basic"], serv)
        # the second service is not used
        self.assertNotIdentical(self.manager.namedServices["basic"], serv2)

        # reconfigServiceWithConstructorArgs was called with new config
        self.assertEqual(serv.config, ((1,), dict(a=4)))

    def testNoName(self):
        self.assertRaises(ValueError, lambda: MyService(1, a=2))

    def testChecksDone(self):
        self.assertRaises(
            config.ConfigErrors, lambda: MyService(1, name="foo"))

    @defer.inlineCallbacks
    def testReconfigWithNew(self):
        serv = yield self.prepareService()

        # reconfigure with the new service
        serv2 = MyService(1, a=4, name="basic2")
        self.master.config.services['basic2'] = serv2

        # the second service is not there yet
        self.assertIdentical(self.manager.namedServices.get("basic2"), None)

        # reconfigure the master
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)

        # the first service is still used
        self.assertIdentical(self.manager.namedServices["basic"], serv)
        # the second service is created
        self.assertIdentical(self.manager.namedServices["basic2"], serv2)

        # reconfigServiceWithConstructorArgs was called with new config
        self.assertEqual(serv2.config, ((1,), dict(a=4)))

    @defer.inlineCallbacks
    def testReconfigWithDeleted(self):
        serv = yield self.prepareService()
        self.assertEqual(serv.running, True)

        # remove all
        self.master.config.services = {}

        # reconfigure the master
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)

        # the first service is still used
        self.assertIdentical(self.manager.namedServices.get("basic"), None)
        self.assertEqual(serv.running, False)

    @defer.inlineCallbacks
    def testConfigDict(self):
        yield self.prepareService()
        self.assertEqual(self.manager.getConfigDict(), {
            'childs': [{
                'args': (1,),
                'class': 'buildbot.test.unit.test_util_service.MyService',
                'kwargs': {'a': 2},
                'name': 'basic'}],
            'name': 'services'})


class UnderTestSharedService(service.SharedService):
    def __init__(self, arg1=None):
        service.SharedService.__init__(self)


class UnderTestDependentService(service.AsyncService):
    @defer.inlineCallbacks
    def startService(self):
        self.dependent = yield UnderTestSharedService.getService(self.parent)

    def stopService(self):
        assert self.dependent.running


class SharedService(unittest.SynchronousTestCase):
    def test_bad_constructor(self):
        parent = service.AsyncMultiService()
        self.failureResultOf(UnderTestSharedService.getService(parent, arg2="foo"))

    def test_creation(self):
        parent = service.AsyncMultiService()
        r = self.successResultOf(UnderTestSharedService.getService(parent))
        r2 = self.successResultOf(UnderTestSharedService.getService(parent))
        r3 = self.successResultOf(UnderTestSharedService.getService(parent, "arg1"))
        r4 = self.successResultOf(UnderTestSharedService.getService(parent, "arg1"))
        self.assertIdentical(r, r2)
        self.assertNotIdentical(r, r3)
        self.assertIdentical(r3, r4)
        self.assertEqual(len(list(iter(parent))), 2)

    def test_startup(self):
        """the service starts when parent starts and stop"""
        parent = service.AsyncMultiService()
        r = self.successResultOf(UnderTestSharedService.getService(parent))
        self.assertEqual(r.running, 0)
        self.successResultOf(parent.startService())
        self.assertEqual(r.running, 1)
        self.successResultOf(parent.stopService())
        self.assertEqual(r.running, 0)

    def test_already_started(self):
        """the service starts during the getService if parent already started"""
        parent = service.AsyncMultiService()
        self.successResultOf(parent.startService())
        r = self.successResultOf(UnderTestSharedService.getService(parent))
        self.assertEqual(r.running, 1)
        # then we stop the parent, and the shared service stops
        self.successResultOf(parent.stopService())
        self.assertEqual(r.running, 0)

    def test_already_stopped_last(self):
        parent = service.AsyncMultiService()
        o = UnderTestDependentService()
        o.setServiceParent(parent)
        self.successResultOf(parent.startService())
        self.successResultOf(parent.stopService())
