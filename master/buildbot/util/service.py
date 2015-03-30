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
from twisted.internet import defer
from twisted.internet import task
from twisted.python import log

from buildbot import util
from buildbot.util import config


class ReconfigurableServiceMixin:

    reconfig_priority = 128

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        if not service.IServiceCollection.providedBy(self):
            return

        # get a list of child services to reconfigure
        reconfigurable_services = [svc
                                   for svc in self
                                   if isinstance(svc, ReconfigurableServiceMixin)]

        # sort by priority
        reconfigurable_services.sort(key=lambda svc: -svc.reconfig_priority)

        for svc in reconfigurable_services:
            yield svc.reconfigServiceWithBuildbotConfig(new_config)


class ClusteredService(service.Service, util.ComparableMixin):

    compare_attrs = ('name',)

    POLL_INTERVAL_SEC = 5 * 60  # 5 minutes

    serviceid = None
    active = False

    def __init__(self, name):
        # service.Service.__init__(self)  # there is none, oddly

        name = util.ascii2unicode(name)
        self.setName(name)

        self.serviceid = None
        self.active = False

    # activity handling

    def isActive(self):
        return self.active

    def activate(self):
        # will run when this instance becomes THE CHOSEN ONE for the cluster
        return defer.succeed(None)

    def deactivate(self):
        # to be overriden by subclasses
        # will run when this instance loses its chosen status
        return defer.succeed(None)

    # service arbitration hooks

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

    # default implementation to delegate to the above methods

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
            log.err(_why='WARNING: ClusteredService(%s) failed during activity poll' % self.name)


class AsyncService(service.Service):

    @defer.inlineCallbacks
    def setServiceParent(self, parent):
        if self.parent is not None:
            yield self.disownServiceParent()
        parent = service.IServiceCollection(parent, parent)
        self.parent = parent
        yield self.parent.addService(self)


class AsyncMultiService(AsyncService, service.MultiService):

    def startService(self):
        service.Service.startService(self)

        return defer.gatherResults(
            [defer.maybeDeferred(svc.startService) for svc in self],
            consumeErrors=True)

    def stopService(self):
        service.Service.stopService(self)

        # unlike MultiService, consume errors in each individual deferred, and
        # pass the first error in a child service up to our caller
        return defer.gatherResults(
            [defer.maybeDeferred(svc.startService) for svc in reversed(list(self))],
            consumeErrors=True)

    def addService(self, service):
        if service.name is not None:
            if service.name in self.namedServices:
                raise RuntimeError("cannot have two services with same name"
                                   " '%s'" % service.name)
            self.namedServices[service.name] = service
        self.services.append(service)
        if self.running:
            # It may be too late for that, but we will do our best
            service.privilegedStartService()
            return service.startService()
        else:
            return defer.succeed(None)


class BuildbotService(AsyncMultiService, config.ConfiguredMixin,
                      ReconfigurableServiceMixin, util.ComparableMixin):
    compare_attrs = ('name', '_config_args', '_config_kwargs', 'config_attr')
    config_attr = "services"
    name = None
    configured = False

    def __init__(self, *args, **kwargs):
        name = kwargs.pop("name", self.name)
        if name is None:
            raise ValueError("%s: must pass a name to constructor" % type(self))

        self.name = name

        self.checkConfig(*args, **kwargs)
        self._config_args = args
        self._config_kwargs = kwargs
        AsyncMultiService.__init__(self)

    def getConfigDict(self):
        _type = type(self)
        return {
            'name': self.name,
            'class': '%s.%s' % (_type.__module__, _type.__name__),
            'args': self._config_args,
            'kwargs': self._config_kwargs
        }

    def reconfigServiceWithBuildbotConfig(self, new_config):
        # get from the config object its sibling config
        config_sibling = getattr(new_config, self.config_attr)[self.name]

        # only reconfigure if different as ComparableMixin says.
        if self.configured and config_sibling == self:
            return defer.succeed(None)
        self.configured = True
        return self.reconfigService(*config_sibling._config_args,
                                    **config_sibling._config_kwargs)

    def setServiceParent(self, parent):
        self.master = parent
        return AsyncService.setServiceParent(self, parent)

    def checkConfig(self, *args, **kwargs):
        return defer.succeed(True)

    def reconfigService(self, *args, **kwargs):
        return defer.succeed(None)
