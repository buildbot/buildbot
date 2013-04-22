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

from twisted.application import service
from twisted.internet import defer, task
from twisted.python import log

from buildbot import util

class ClusteredService(service.Service, util.ComparableMixin):

    compare_attrs = ('name',)

    POLL_INTERVAL_SEC = 5*60 # 5 minutes

    serviceid = None
    active = False

    def __init__(self, name):
        # service.Service.__init__(self)  # there is none, oddly

        name = util.ascii2unicode(name)
        self.setName(name)

        self.serviceid = None
        self.active = False

    ## activity handling

    def isActive(self):
        return self.active

    def activate(self):
    # will run when this instance becomes THE CHOSEN ONE for the cluster
        return defer.succeed(None)

    def deactivate(self):
    # to be overriden by subclasses
    # will run when this instance loses its chosen status
        return defer.succeed(None)

    ## service arbitration hooks

    def _getServiceId(self):
        # retrieve the id for this service; we assume that, once we have a valid id,
        # the id doesnt change. This may return a Deferred.
        raise NotImplementedError

    def _claimService(self):
        # Attempt to claim the service for this master. Should return True or False
        # (optionally via a Deferred) to indicate whether this master now owns the
        # service.
        raise NotImplementedError

    def _unclaimService(self):
        # Release the service from this master. This will only be called by a claimed
        # service, and this really should be robust and release the claim. May return
        # a Deferred.
        raise NotImplementedError

    ## default implementation to delegate to the above methods

    def startService(self):
        # subclasses should override startService only to perform actions that should
        # run on all instances, even if they never get activated on this master.

        service.Service.startService(self)
        self._startActivityPolling()

    def stopService(self):
        # subclasses should override stopService only to perform actions that should
        # run on all instances, even if they never get activated on this master.

        self._stopActivityPolling()

        # need to wait for prior activations to finish
        if self._activityPollDeferred:
            d = self._activityPollDeferred
        else:
            d = defer.succeed(None)

        @d.addCallback
        def deactivate_if_needed(_):
            if self.active:
                self.active = False

                d = defer.maybeDeferred(self.deactivate)
                # no errback here: skip the "unclaim" if the deactivation is uncertain

                d.addCallback(lambda _: defer.maybeDeferred(self._unclaimService))

                d.addErrback(log.err, _why="Caught exception while deactivating ClusteredService(%s)" % self.name)
                return d

        d.addCallback(lambda _: service.Service.stopService(self))
        return d

    def _startActivityPolling(self):
        self._activityPollCall = task.LoopingCall(self._activityPoll)
        # plug in a clock if we have one, for tests
        if hasattr(self, 'clock'):
            self._activityPollCall.clock = self.clock

        d = self._activityPollCall.start(self.POLL_INTERVAL_SEC, now=True)
        self._activityPollDeferred = d

        # this should never happen, but just in case:
        d.addErrback(log.err, 'while polling for service activity:')

    def _stopActivityPolling(self):
        if self._activityPollCall:
            self._activityPollCall.stop()
            self._activityPollCall = None

    @defer.inlineCallbacks
    def _activityPoll(self):
        try:
            # just in case..
            if self.active:
                return

            if self.serviceid is None:
                self.serviceid = yield self._getServiceId()

            try:
                claimed = yield self._claimService()
            except Exception:
                log.err(_why='WARNING: ClusteredService(%s) got exception while trying to claim' % self.name)
                return

            if not claimed:
                return

            self._stopActivityPolling()
            self.active = True
            try:
                yield self.activate()
            except Exception:
                # this service is half-active, and noted as such in the db..
                log.err(_why='WARNING: ClusteredService(%s) is only partially active' % self.name)

        except Exception:
            # don't pass exceptions into LoopingCall, which can cause it to fail
            pass
