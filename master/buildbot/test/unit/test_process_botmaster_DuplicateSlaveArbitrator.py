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

import mock
from twisted.python import failure, log
from twisted.trial import unittest
from twisted.internet import defer, reactor, task
from twisted.spread import pb
from buildbot.test.util import compat
from buildbot.process import botmaster
from buildbot.util.eventual import eventually

# TODO: should do this with more of the Twisted machinery intact - maybe in a
# separate integration test?

class FakeAbstractBuildSlave(object):

    def __init__(self, slave, name, isConnected=True, reactor=reactor):
        self.slavename = name
        self.slave = slave
        self.isConnectedResult = isConnected
        self.reactor = reactor
        self.call_on_detach = lambda : None

        # set up for loseConnection to cause the slave to detach, but not
        # immediately
        def tport_loseConnection():
            self.isConnectedResult = False
            self.call_on_detach()
            self.call_on_detach = None
        self.slave.broker.transport.loseConnection = (lambda :
                eventually(tport_loseConnection))

    def subscribeToDetach(self, callback):
        self.call_on_detach = callback

    def isConnected(self):
        return self.isConnectedResult


class FakeRemoteBuildSlave(object):

    def __init__(self, name, callRemoteFailure=False,
                             callRemoteException=False,
                             callRemoteHang=0,
                             reactor=reactor):
        self.name = name
        self.callRemoteFailure = callRemoteFailure
        self.callRemoteException = callRemoteException
        self.callRemoteHang = callRemoteHang
        self.reactor = reactor

        self.broker = mock.Mock()
        self.broker.transport.getPeer = lambda : "<peer %s>" % name

    def _makePingResult(self):
        if self.callRemoteException:
            exc = self.callRemoteException()
            log.msg(" -> exception %r" % (exc,))
            raise exc
        if self.callRemoteFailure:
            f = defer.fail(self.callRemoteFailure())
            log.msg(" -> failure %r" % (f,))
            return f
        return defer.succeed(None)

    def callRemote(self, meth, *args, **kwargs):
        assert meth == "print"
        log.msg("%r.callRemote('print', %r)" % (self, args[0],))
        # if we're asked to hang, then set up to fire the deferred later
        if self.callRemoteHang:
            log.msg(" -> hang for %d s" % (self.callRemoteHang,))
            d = defer.Deferred()
            self.reactor.callLater(self.callRemoteHang, d.callback, None)
            def hangdone(_):
                log.msg("%r.callRemote hang finished" % (self,))
                return self._makePingResult()
            d.addCallback(hangdone)
            self.callRemote_d = d
        # otherwise, return a fired deferred
        else:
            self.callRemote_d = self._makePingResult()
        return self.callRemote_d

    def __repr__(self):
        return "<FakeRemoteBuildSlave %s>" % (self.name,)


class DuplicateSlaveArbitrator(unittest.TestCase):

    def makeDeadReferenceError(self):
        return pb.DeadReferenceError("Calling Stale Broker (fake exception)")

    def makeRuntimeError(self):
        return RuntimeError("oh noes!")

    def makePBConnectionLostFailure(self):
        return failure.Failure(pb.PBConnectionLost("gone"))

    def test_old_slave_present(self):
        old_remote = FakeRemoteBuildSlave("old")
        new_remote = FakeRemoteBuildSlave("new")
        buildslave = FakeAbstractBuildSlave(old_remote, name="testslave")
        arb = botmaster.DuplicateSlaveArbitrator(buildslave)
        d = arb.getPerspective(new_remote, "testslave")
        def got_persp(bs):
            self.fail("shouldn't get here")
        def failed(f):
            f.trap(RuntimeError) # expected error
        d.addCallbacks(got_persp, failed)
        return d

    def test_old_slave_absent_deadref_exc(self):
        old_remote = FakeRemoteBuildSlave("old",
                callRemoteException=self.makeDeadReferenceError)
        new_remote = FakeRemoteBuildSlave("new")
        buildslave = FakeAbstractBuildSlave(old_remote, name="testslave")
        arb = botmaster.DuplicateSlaveArbitrator(buildslave)
        d = arb.getPerspective(new_remote, "testslave")
        def got_persp(bs):
            self.assertIdentical(bs, buildslave)
        d.addCallback(got_persp)
        return d

    def test_old_slave_absent_connlost_failure(self):
        old_remote = FakeRemoteBuildSlave("old",
                callRemoteFailure=self.makePBConnectionLostFailure)
        new_remote = FakeRemoteBuildSlave("new")
        buildslave = FakeAbstractBuildSlave(old_remote, name="testslave")
        arb = botmaster.DuplicateSlaveArbitrator(buildslave)
        d = arb.getPerspective(new_remote, "testslave")
        def got_persp(bs):
            self.assertIdentical(bs, buildslave)
        d.addCallback(got_persp)
        return d

    @compat.usesFlushLoggedErrors
    def test_old_slave_absent_unexpected_exc(self):
        old_remote = FakeRemoteBuildSlave("old",
                callRemoteException=self.makeRuntimeError)
        new_remote = FakeRemoteBuildSlave("new")
        buildslave = FakeAbstractBuildSlave(old_remote, name="testslave")
        arb = botmaster.DuplicateSlaveArbitrator(buildslave)
        d = arb.getPerspective(new_remote, "testslave")
        def got_persp(bs):
            # getPerspective has returned successfully:
            self.assertIdentical(bs, buildslave)
            # and the unexpected RuntimeError was logged:
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        d.addCallback(got_persp)
        return d

    def do_test_old_slave_absent_timeout(self, callRemoteException=None):
        clock = task.Clock()
        PING_TIMEOUT = botmaster.DuplicateSlaveArbitrator.PING_TIMEOUT

        old_remote = FakeRemoteBuildSlave("old", reactor=clock,
                callRemoteHang=PING_TIMEOUT+1,
                callRemoteException=callRemoteException)
        new_remote = FakeRemoteBuildSlave("new")
        buildslave = FakeAbstractBuildSlave(old_remote, name="testslave",
                reactor=clock)
        arb = botmaster.DuplicateSlaveArbitrator(buildslave)
        arb._reactor = clock
        d = arb.getPerspective(new_remote, "testslave")
        def got_persp(bs):
            self.assertIdentical(bs, buildslave)
        d.addCallback(got_persp)

        # show the passage of time for 2s more than the PING_TIMEOUT, to allow
        # the old callRemote to return eventually
        clock.pump([.1] * 10 * (PING_TIMEOUT+4))

        # check that the timed-out call eventually returned (and was ignored,
        # even if there was an exception)
        self.failUnless(old_remote.callRemote_d.called)

        return d

    def test_old_slave_absent_timeout(self):
        return self.do_test_old_slave_absent_timeout()

    def test_old_slave_absent_timeout_exc(self):
        return self.do_test_old_slave_absent_timeout(
                callRemoteException=self.makeRuntimeError)

    @compat.usesFlushLoggedErrors
    def test_new_slave_ping_error(self):
        old_remote = FakeRemoteBuildSlave("old")
        new_remote = FakeRemoteBuildSlave("new",
                callRemoteException=self.makeRuntimeError)
        buildslave = FakeAbstractBuildSlave(old_remote, name="testslave")
        arb = botmaster.DuplicateSlaveArbitrator(buildslave)
        d = arb.getPerspective(new_remote, "testslave")
        def got_persp(bs):
            self.fail("shouldn't get here")
        def failed(f):
            pass #f.trap(RuntimeError) # expected error
        d.addCallbacks(got_persp, failed)
        return d

