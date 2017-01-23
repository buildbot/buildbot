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

import textwrap

from twisted.application import internet
from twisted.internet import defer
from twisted.python import log

from buildbot import util
from buildbot.db import builders
from buildbot.db import buildrequests
from buildbot.db import builds
from buildbot.db import buildsets
from buildbot.db import changes
from buildbot.db import changesources
from buildbot.db import enginestrategy
from buildbot.db import exceptions
from buildbot.db import logs
from buildbot.db import masters
from buildbot.db import model
from buildbot.db import pool
from buildbot.db import schedulers
from buildbot.db import sourcestamps
from buildbot.db import state
from buildbot.db import steps
from buildbot.db import tags
from buildbot.db import users
from buildbot.db import workers
from buildbot.util import service
from buildbot.worker_transition import WorkerAPICompatMixin


upgrade_message = textwrap.dedent("""\

    The Buildmaster database needs to be upgraded before this version of
    buildbot can run.  Use the following command-line

        buildbot upgrade-master {basedir}

    to upgrade the database, and try starting the buildmaster again.  You may
    want to make a backup of your buildmaster before doing so.
    """).strip()


class DBConnector(WorkerAPICompatMixin, service.ReconfigurableServiceMixin,
                  service.AsyncMultiService):
    # The connection between Buildbot and its backend database.  This is
    # generally accessible as master.db, but is also used during upgrades.
    #
    # Most of the interesting operations available via the connector are
    # implemented in connector components, available as attributes of this
    # object, and listed below.

    # Period, in seconds, of the cleanup task.  This master will perform
    # periodic cleanup actions on this schedule.
    CLEANUP_PERIOD = 3600

    def __init__(self, basedir):
        service.AsyncMultiService.__init__(self)
        self.setName('db')
        self.basedir = basedir

        # not configured yet - we don't build an engine until the first
        # reconfig
        self.configured_url = None

        # set up components
        self._engine = None  # set up in reconfigService
        self.pool = None  # set up in reconfigService

    def setServiceParent(self, p):
        d = service.AsyncMultiService.setServiceParent(self, p)
        self.model = model.Model(self)
        self.changes = changes.ChangesConnectorComponent(self)
        self.changesources = changesources.ChangeSourcesConnectorComponent(
            self)
        self.schedulers = schedulers.SchedulersConnectorComponent(self)
        self.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self)
        self.buildsets = buildsets.BuildsetsConnectorComponent(self)
        self.buildrequests = buildrequests.BuildRequestsConnectorComponent(
            self)
        self.state = state.StateConnectorComponent(self)
        self.builds = builds.BuildsConnectorComponent(self)
        self.workers = workers.WorkersConnectorComponent(self)
        self._registerOldWorkerAttr("workers", name="buildslaves")
        self.users = users.UsersConnectorComponent(self)
        self.masters = masters.MastersConnectorComponent(self)
        self.builders = builders.BuildersConnectorComponent(self)
        self.steps = steps.StepsConnectorComponent(self)
        self.tags = tags.TagsConnectorComponent(self)
        self.logs = logs.LogsConnectorComponent(self)

        self.cleanup_timer = internet.TimerService(self.CLEANUP_PERIOD,
                                                   self._doCleanup)
        self.cleanup_timer.clock = self.master.reactor
        self.cleanup_timer.setServiceParent(self)
        return d

    @defer.inlineCallbacks
    def setup(self, check_version=True, verbose=True):
        db_url = self.configured_url = self.master.config.db['db_url']

        log.msg("Setting up database with URL %r"
                % util.stripUrlPassword(db_url))

        # set up the engine and pool
        self._engine = enginestrategy.create_engine(db_url,
                                                    basedir=self.basedir)
        self.pool = pool.DBThreadPool(
            self._engine, reactor=self.master.reactor, verbose=verbose)

        # make sure the db is up to date, unless specifically asked not to
        if check_version:
            current = yield self.model.is_current()
            if not current:
                for l in upgrade_message.format(basedir=self.master.basedir).split('\n'):
                    log.msg(l)
                raise exceptions.DatabaseNotReadyError()

    def reconfigServiceWithBuildbotConfig(self, new_config):
        # double-check -- the master ensures this in config checks
        assert self.configured_url == new_config.db['db_url']

        return service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                    new_config)

    def _doCleanup(self):
        """
        Perform any periodic database cleanup tasks.

        @returns: Deferred
        """
        # pass on this if we're not configured yet
        if not self.configured_url:
            return

        d = self.changes.pruneChanges(self.master.config.changeHorizon)
        d.addErrback(log.err, 'while pruning changes')
        return d
