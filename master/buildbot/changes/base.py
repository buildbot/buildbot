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
from twisted.python import log
from zope.interface import implementer

from buildbot import config
from buildbot.interfaces import IChangeSource
from buildbot.util import service
from buildbot.util.poll import method as poll_method
from buildbot.warnings import warn_deprecated


@implementer(IChangeSource)
class ChangeSource(service.ClusteredBuildbotService):

    def describe(self):
        pass

    # activity handling

    def activate(self):
        return defer.succeed(None)

    def deactivate(self):
        return defer.succeed(None)

    # service handling

    def _getServiceId(self):
        return self.master.data.updates.findChangeSourceId(self.name)

    def _claimService(self):
        return self.master.data.updates.trySetChangeSourceMaster(self.serviceid,
                                                                 self.master.masterid)

    def _unclaimService(self):
        return self.master.data.updates.trySetChangeSourceMaster(self.serviceid,
                                                                 None)


class ReconfigurablePollingChangeSource(ChangeSource):
    pollInterval = None
    pollAtLaunch = None
    pollRandomDelayMin = None
    pollRandomDelayMax = None

    def checkConfig(self, name=None, pollInterval=60 * 10, pollAtLaunch=False,
                    pollRandomDelayMin=0, pollRandomDelayMax=0):
        super().checkConfig(name=name)
        if pollInterval < 0:
            config.error(f"interval must be >= 0: {pollInterval}")
        if pollRandomDelayMin < 0:
            config.error(f"min random delay must be >= 0: {pollRandomDelayMin}")
        if pollRandomDelayMax < 0:
            config.error(f"max random delay must be >= 0: {pollRandomDelayMax}")
        if pollRandomDelayMin > pollRandomDelayMax:
            config.error(f"min random delay must be <= {pollRandomDelayMax}: {pollRandomDelayMin}")
        if pollRandomDelayMax >= pollInterval:
            config.error(f"max random delay must be < {pollInterval}: {pollRandomDelayMax}")

    @defer.inlineCallbacks
    def reconfigService(self, name=None, pollInterval=60 * 10, pollAtLaunch=False,
                        pollRandomDelayMin=0, pollRandomDelayMax=0):
        self.pollInterval, prevPollInterval = pollInterval, self.pollInterval
        self.pollAtLaunch = pollAtLaunch
        self.pollRandomDelayMin = pollRandomDelayMin
        self.pollRandomDelayMax = pollRandomDelayMax
        yield super().reconfigService(name=name)

        # pollInterval change is the only value which makes sense to reconfigure check.
        if prevPollInterval != pollInterval and self.doPoll.running:
            yield self.doPoll.stop()
            # As a implementation detail, poller will 'pollAtReconfigure' if poll interval changes
            # and pollAtLaunch=True
            yield self.doPoll.start(interval=self.pollInterval, now=self.pollAtLaunch,
                                    random_delay_min=self.pollRandomDelayMin,
                                    random_delay_max=self.pollRandomDelayMax)

    def poll(self):
        pass

    @poll_method
    def doPoll(self):
        d = defer.maybeDeferred(self.poll)
        d.addErrback(log.err, f'{self}: while polling for changes')
        return d

    def force(self):
        self.doPoll()

    def activate(self):
        self.doPoll.start(interval=self.pollInterval, now=self.pollAtLaunch,
                          random_delay_min=self.pollRandomDelayMin,
                          random_delay_max=self.pollRandomDelayMax)

    def deactivate(self):
        return self.doPoll.stop()


class PollingChangeSource(ReconfigurablePollingChangeSource):
    # Legacy code will be very painful to port to BuildbotService life cycle
    # because the unit tests keep doing shortcuts for the Service life cycle (i.e by no calling
    # startService) instead of porting everything at once, we make a class to support legacy

    def checkConfig(self, name=None, pollInterval=60 * 10, pollAtLaunch=False,
                    pollRandomDelayMin=0, pollRandomDelayMax=0, **kwargs):
        super().checkConfig(name=name, pollInterval=60 * 10, pollAtLaunch=False,
                            pollRandomDelayMin=0, pollRandomDelayMax=0)

        warn_deprecated('3.3.0', 'PollingChangeSource has been deprecated: ' +
                        'please use ReconfigurablePollingChangeSource')

        self.pollInterval = pollInterval
        self.pollAtLaunch = pollAtLaunch
        self.pollRandomDelayMin = pollRandomDelayMin
        self.pollRandomDelayMax = pollRandomDelayMax

    def reconfigService(self, *args, **kwargs):
        # BuildbotServiceManager will detect such exception and swap old service with new service,
        # instead of just reconfiguring
        raise NotImplementedError()
