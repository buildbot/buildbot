# This file is part of Buildbot. Buildbot is free software: you can
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

import hashlib

from twisted.application import service
from twisted.internet import defer
from twisted.internet import task
from twisted.python import log
from twisted.python import reflect
from twisted.python.reflect import accumulateClassList

from buildbot import util
from buildbot.util import bytes2unicode
from buildbot.util import config
from buildbot.util import unicode2bytes


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


# twisted 16's Service is now an new style class, better put everybody new style
# to catch issues even on twisted < 16
class AsyncService(service.Service):

    # service.Service.setServiceParent does not wait for neither disownServiceParent nor addService
    # to complete
    @defer.inlineCallbacks
    def setServiceParent(self, parent):
        if self.parent is not None:
            yield self.disownServiceParent()
        parent = service.IServiceCollection(parent, parent)
        self.parent = parent
        yield self.parent.addService(self)

    # service.Service.disownServiceParent does not wait for removeService to complete before
    # setting parent to None
    @defer.inlineCallbacks
    def disownServiceParent(self):
        yield self.parent.removeService(self)
        self.parent = None

    # We recurse over the parent services until we find a MasterService
    @property
    def master(self):
        if self.parent is None:
            return None
        return self.parent.master


class AsyncMultiService(AsyncService, service.MultiService):

    def startService(self):
        # Do NOT use super() here.
        # The method resolution order would cause MultiService.startService() to
        # be called which we explicitly want to override with this method.
        service.Service.startService(self)
        dl = []
        # if a service attaches another service during the reconfiguration
        # then the service will be started twice, so we don't use iter, but rather
        # copy in a list
        for svc in list(self):
            # handle any deferreds, passing up errors and success
            dl.append(defer.maybeDeferred(svc.startService))
        return defer.gatherResults(dl, consumeErrors=True)

    @defer.inlineCallbacks
    def stopService(self):
        # Do NOT use super() here.
        # The method resolution order would cause MultiService.stopService() to
        # be called which we explicitly want to override with this method.
        service.Service.stopService(self)
        services = list(self)
        services.reverse()
        dl = []
        for svc in services:
            if not isinstance(svc, SharedService):
                dl.append(defer.maybeDeferred(svc.stopService))
        # unlike MultiService, consume errors in each individual deferred, and
        # pass the first error in a child service up to our caller
        yield defer.gatherResults(dl, consumeErrors=True)
        for svc in services:
            if isinstance(svc, SharedService):
                yield svc.stopService()

    def addService(self, service):
        if service.name is not None:
            if service.name in self.namedServices:
                raise RuntimeError("cannot have two services with same name"
                                   f" '{service.name}'")
            self.namedServices[service.name] = service
        self.services.append(service)
        if self.running:
            # It may be too late for that, but we will do our best
            service.privilegedStartService()
            return service.startService()
        return defer.succeed(None)


class MasterService(AsyncMultiService):
    # master service is the service that stops the master property recursion

    @property
    def master(self):
        return self


class SharedService(AsyncMultiService):
    """a service that is created only once per parameter set in a parent service"""

    @classmethod
    @defer.inlineCallbacks
    def getService(cls, parent, *args, **kwargs):
        name = cls.getName(*args, **kwargs)
        if name in parent.namedServices:
            return parent.namedServices[name]

        instance = cls(*args, **kwargs)

        # The class is not required to initialized its name
        # but we use the name to identify the instance in the parent service
        # so we force it with the name we used
        instance.name = name
        yield instance.setServiceParent(parent)

        # we put the service on top of the list, so that it is stopped the last
        # This make sense as the shared service is used as a dependency
        # for other service
        parent.services.remove(instance)
        parent.services.insert(0, instance)
        # hook the return value to the instance object
        return instance

    @classmethod
    def getName(cls, *args, **kwargs):
        _hash = hashlib.sha1()
        for arg in args:
            arg = unicode2bytes(str(arg))
            _hash.update(arg)
        for k, v in sorted(kwargs.items()):
            k = unicode2bytes(str(k))
            v = unicode2bytes(str(v))
            _hash.update(k)
            _hash.update(v)
        return cls.__name__ + "_" + _hash.hexdigest()


class BuildbotService(AsyncMultiService, config.ConfiguredMixin, util.ComparableMixin,
                      ReconfigurableServiceMixin):
    compare_attrs = ('name', '_config_args', '_config_kwargs')
    name = None
    configured = False
    objectid = None

    def __init__(self, *args, **kwargs):
        name = kwargs.pop("name", None)
        if name is not None:
            self.name = bytes2unicode(name)
        self.checkConfig(*args, **kwargs)
        if self.name is None:
            raise ValueError(f"{type(self)}: must pass a name to constructor")
        self._config_args = args
        self._config_kwargs = kwargs
        self.rendered = False
        super().__init__()

    def getConfigDict(self):
        _type = type(self)
        return {'name': self.name,
                'class': _type.__module__ + "." + _type.__name__,
                'args': self._config_args,
                'kwargs': self._config_kwargs}

    @defer.inlineCallbacks
    def reconfigServiceWithSibling(self, sibling):
        # only reconfigure if sibling is configured differently.
        # sibling == self is using ComparableMixin's implementation
        # only compare compare_attrs
        if self.configured and util.ComparableMixin.isEquivalent(sibling, self):
            return None
        self.configured = True
        # render renderables in parallel
        # Properties import to resolve cyclic import issue
        from buildbot.process.properties import Properties
        p = Properties()
        p.master = self.master
        # render renderables in parallel
        secrets = []
        kwargs = {}
        accumulateClassList(self.__class__, 'secrets', secrets)
        for k, v in sibling._config_kwargs.items():
            if k in secrets:
                # for non reconfigurable services, we force the attribute
                v = yield p.render(v)
                setattr(sibling, k, v)
                setattr(self, k, v)
            kwargs[k] = v

        d = yield self.reconfigService(*sibling._config_args,
                                       **kwargs)
        return d

    def canReconfigWithSibling(self, sibling):
        return reflect.qual(self.__class__) == reflect.qual(sibling.__class__)

    def configureService(self):
        # reconfigServiceWithSibling with self, means first configuration
        return self.reconfigServiceWithSibling(self)

    @defer.inlineCallbacks
    def startService(self):
        if not self.configured:
            try:
                yield self.configureService()
            except NotImplementedError:
                pass
        yield super().startService()

    def checkConfig(self, *args, **kwargs):
        return defer.succeed(True)

    def reconfigService(self, name=None, *args, **kwargs):
        return defer.succeed(None)

    def renderSecrets(self, *args):
        # Properties import to resolve cyclic import issue
        from buildbot.process.properties import Properties
        p = Properties()
        p.master = self.master

        if len(args) == 1:
            return p.render(args[0])

        return defer.gatherResults([p.render(s) for s in args], consumeErrors=True)


class ClusteredBuildbotService(BuildbotService):

    """
    ClusteredBuildbotService-es are meant to be executed on a single
    master only. When starting such a service, by means of "yield startService",
    it will first try to claim it on the current master and:
    - return without actually starting it
      if it was already claimed by another master (self.active == False).
      It will however keep trying to claim it, in case another master
      stops, and takes the job back.
    - return after it starts else.
    """
    compare_attrs = ('name',)

    POLL_INTERVAL_SEC = 5 * 60  # 5 minutes

    serviceid = None
    active = False

    def __init__(self, *args, **kwargs):

        self.serviceid = None
        self.active = False
        self._activityPollCall = None
        self._activityPollDeferred = None
        super().__init__(*args, **kwargs)

    # activity handling

    def isActive(self):
        return self.active

    def activate(self):
        # will run when this instance becomes THE CHOSEN ONE for the cluster
        return defer.succeed(None)

    def deactivate(self):
        # to be overridden by subclasses
        # will run when this instance loses its chosen status
        return defer.succeed(None)

    # service arbitration hooks

    def _getServiceId(self):
        # retrieve the id for this service; we assume that, once we have a valid id,
        # the id doesn't change. This may return a Deferred.
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

    @defer.inlineCallbacks
    def startService(self):
        # subclasses should override startService only to perform actions that should
        # run on all instances, even if they never get activated on this
        # master.
        yield super().startService()
        self._startServiceDeferred = defer.Deferred()
        self._startActivityPolling()
        yield self._startServiceDeferred

    @defer.inlineCallbacks
    def stopService(self):
        # subclasses should override stopService only to perform actions that should
        # run on all instances, even if they never get activated on this
        # master.

        self._stopActivityPolling()

        # need to wait for prior activations to finish
        if self._activityPollDeferred:
            yield self._activityPollDeferred

        if self.active:
            self.active = False

            try:
                yield self.deactivate()
                yield self._unclaimService()
            except Exception as e:
                msg = f"Caught exception while deactivating ClusteredService({self.name})"
                log.err(e, _why=msg)

        yield super().stopService()

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
            return self._activityPollDeferred
        return None

    def _callbackStartServiceDeferred(self):
        if self._startServiceDeferred is not None:
            self._startServiceDeferred.callback(None)
            self._startServiceDeferred = None

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
                msg = f'WARNING: ClusteredService({self.name}) got exception while trying to claim'
                log.err(_why=msg)
                return

            if not claimed:
                # this master is not responsible
                # for this service, we callback for StartService
                # if it was not callback-ed already,
                # and keep polling to take back the service
                # if another one lost it
                self._callbackStartServiceDeferred()
                return

            try:
                # this master is responsible for this service
                # we activate it
                self.active = True
                yield self.activate()
            except Exception:
                # this service is half-active, and noted as such in the db..
                msg = f'WARNING: ClusteredService({self.name}) is only partially active'
                log.err(_why=msg)
            finally:
                # cannot wait for its deactivation
                # with yield self._stopActivityPolling
                # as we're currently executing the
                # _activityPollCall callback
                # we just call it without waiting its stop
                # (that may open race conditions)
                self._stopActivityPolling()
                self._callbackStartServiceDeferred()
        except Exception:
            # don't pass exceptions into LoopingCall, which can cause it to
            # fail
            msg = f'WARNING: ClusteredService({self.name}) failed during activity poll'
            log.err(_why=msg)


class BuildbotServiceManager(AsyncMultiService, config.ConfiguredMixin,
                             ReconfigurableServiceMixin):
    config_attr = "services"
    name = "services"

    def getConfigDict(self):
        return {'name': self.name,
                'childs': [v.getConfigDict()
                           for v in self.namedServices.values()]}

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):

        # arrange childs by name
        old_by_name = self.namedServices
        old_set = set(old_by_name)
        new_config_attr = getattr(new_config, self.config_attr)
        if isinstance(new_config_attr, list):
            new_by_name = {s.name: s
                           for s in new_config_attr}
        elif isinstance(new_config_attr, dict):
            new_by_name = new_config_attr
        else:
            raise TypeError(f"config.{self.config_attr} should be a list or dictionary")
        new_set = set(new_by_name)

        # calculate new childs, by name, and removed childs
        removed_names, added_names = util.diffSets(old_set, new_set)

        # find any children for which the old instance is not
        # able to do a reconfig with the new sibling
        # and add them to both removed and added, so that we
        # run the new version
        for n in old_set & new_set:
            old = old_by_name[n]
            new = new_by_name[n]
            # check if we are able to reconfig service
            if not old.canReconfigWithSibling(new):
                removed_names.add(n)
                added_names.add(n)

        if removed_names or added_names:
            log.msg(f"adding {len(added_names)} new {self.config_attr}, "
                    f"removing {len(removed_names)}")

            for n in removed_names:
                child = old_by_name[n]
                # disownServiceParent calls stopService after removing the relationship
                # as child might use self.master.data to stop itself, its better to stop it first
                # (this is related to the fact that self.master is found by recursively looking at
                # self.parent for a master)
                yield child.stopService()
                # it has already called, so do not call it again
                child.stopService = lambda: None
                yield child.disownServiceParent()

            for n in added_names:
                child = new_by_name[n]
                # setup service's objectid
                if hasattr(child, 'objectid'):
                    class_name = f'{child.__class__.__module__}.{child.__class__.__name__}'
                    objectid = yield self.master.db.state.getObjectId(
                        child.name, class_name)
                    child.objectid = objectid
                yield child.setServiceParent(self)

        # As the services that were just added got
        # reconfigServiceWithSibling called by
        # setServiceParent->startService,
        # we avoid calling it again by selecting
        # in reconfigurable_services, services
        # that were not added just now
        reconfigurable_services = [svc for svc in self
                                   if svc.name not in added_names]
        # sort by priority
        reconfigurable_services.sort(key=lambda svc: -svc.reconfig_priority)

        for svc in reconfigurable_services:
            if not svc.name:
                raise ValueError(f"{self}: child {svc} should have a defined name attribute")
            config_sibling = new_by_name.get(svc.name)
            try:
                yield svc.reconfigServiceWithSibling(config_sibling)
            except NotImplementedError:
                # legacy support. Its too painful to transition old code to new Service life cycle
                # so we implement switch of child when the service raises NotImplementedError
                # Note this means that self will stop, and sibling will take ownership
                # means that we have a small time where the service is unavailable.
                yield svc.disownServiceParent()
                config_sibling.objectid = svc.objectid
                yield config_sibling.setServiceParent(self)
            except Exception as e:  # pragma: no cover
                log.err(e, f'Got exception while reconfiguring {self} child service {svc.name}:\n'
                        f'current config dict:\n{svc.getConfigDict()}\n'
                        f'new config dict:\n{config_sibling.getConfigDict()}')
                raise
