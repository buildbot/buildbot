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
#
from __future__ import absolute_import
from __future__ import print_function

import datetime

from twisted.internet import defer

from buildbot.config import BuilderConfig
from buildbot.configurators import ConfiguratorBase
from buildbot.process.buildstep import BuildStep
from buildbot.process.factory import BuildFactory
from buildbot.process.results import SUCCESS
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.schedulers.timed import Nightly
from buildbot.util import datetime2epoch
from buildbot.worker.local import LocalWorker

""" Janitor is a configurator which create a Janitor Builder with all needed Janitor steps
"""

JANITOR_NAME = "__Janitor"  # If you read this code, you may want to patch this name.


def now():
    """patchable now (datetime is not patchable as builtin)"""
    return datetime.datetime.utcnow()


class LogChunksJanitor(BuildStep):
    name = 'LogChunksJanitor'
    renderables = ["logHorizon"]

    def __init__(self, logHorizon):
        BuildStep.__init__(self)
        self.logHorizon = logHorizon

    @defer.inlineCallbacks
    def run(self):
        older_than_timestamp = datetime2epoch(now() - self.logHorizon)
        deleted = yield self.master.db.logs.deleteOldLogChunks(older_than_timestamp)
        self.descriptionDone = ["deleted", str(deleted), "logchunks"]
        defer.returnValue(SUCCESS)


class JanitorConfigurator(ConfiguratorBase):
    def __init__(self, logHorizon=None, hour=0, **kwargs):
        ConfiguratorBase.__init__(self)
        self.logHorizon = logHorizon
        self.hour = hour
        self.kwargs = kwargs

    def configure(self, config_dict):
        if self.logHorizon is None:
            return
        logHorizon = self.logHorizon
        hour = self.hour
        kwargs = self.kwargs

        ConfiguratorBase.configure(self, config_dict)
        nightly_kwargs = {}

        # we take the defaults of Nightly, except for hour
        for arg in ('minute', 'dayOfMonth', 'month', 'dayOfWeek'):
            if arg in kwargs:
                nightly_kwargs[arg] = kwargs[arg]

        self.schedulers.append(Nightly(
            name=JANITOR_NAME, builderNames=[JANITOR_NAME], hour=hour, **nightly_kwargs))

        self.schedulers.append(ForceScheduler(
            name=JANITOR_NAME + "_force",
            builderNames=[JANITOR_NAME]))

        self.builders.append(BuilderConfig(
            name=JANITOR_NAME, workername=JANITOR_NAME, factory=BuildFactory(steps=[
                LogChunksJanitor(logHorizon=logHorizon)
            ])
        ))
        self.protocols.setdefault('null', {})
        self.workers.append(LocalWorker(JANITOR_NAME))
