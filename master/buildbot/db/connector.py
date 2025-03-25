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


import textwrap

from twisted.application import internet
from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot import util
from buildbot.config.master import DBConfig
from buildbot.db import build_data
from buildbot.db import builders
from buildbot.db import buildrequests
from buildbot.db import builds
from buildbot.db import buildsets
from buildbot.db import changes
from buildbot.db import changesources
from buildbot.db import codebase_branches
from buildbot.db import codebase_commits
from buildbot.db import codebases
from buildbot.db import enginestrategy
from buildbot.db import exceptions
from buildbot.db import logs
from buildbot.db import masters
from buildbot.db import model
from buildbot.db import pool
from buildbot.db import projects
from buildbot.db import schedulers
from buildbot.db import sourcestamps
from buildbot.db import state
from buildbot.db import steps
from buildbot.db import tags
from buildbot.db import test_result_sets
from buildbot.db import test_results
from buildbot.db import users
from buildbot.db import workers
from buildbot.util import service
from buildbot.util.deferwaiter import DeferWaiter
from buildbot.util.sautils import get_upsert_method
from buildbot.util.twisted import async_to_deferred

upgrade_message = textwrap.dedent("""\

    The Buildmaster database needs to be upgraded before this version of
    buildbot can run.  Use the following command-line

        buildbot upgrade-master {basedir}

    to upgrade the database, and try starting the buildmaster again.  You may
    want to make a backup of your buildmaster before doing so.
    """).strip()


class DBConnector(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    # The connection between Buildbot and its backend database.  This is
    # generally accessible as master.db, but is also used during upgrades.
    #
    # Most of the interesting operations available via the connector are
    # implemented in connector components, available as attributes of this
    # object, and listed below.
    #
    # DBConnector is not usual Buildbot service because it is not child of the
    # master service. This is because DBConnector must start before all other
    # services and must stop after all other services that may be using it.

    # Period, in seconds, of the cleanup task.  This master will perform
    # periodic cleanup actions on this schedule.
    CLEANUP_PERIOD = 3600

    configured_db_config: DBConfig

    def __init__(self, basedir):
        super().__init__()
        self.setName('db')
        self.basedir = basedir

        # not configured yet - we don't build an engine until the first
        # reconfig
        self.configured_db_config = None

        # set up components
        self._engine = None  # set up in reconfigService
        self.pool = None  # set up in reconfigService
        self.upsert = get_upsert_method(None)  # set up in reconfigService
        self.has_native_upsert = False

        self._master = None

        self._db_tasks_waiter = DeferWaiter()

    @property
    def master(self):
        return self._master

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        new_db_config = yield self.master.get_db_config(new_config)
        if self.configured_db_config is None:
            self.configured_db_config = new_db_config
        elif self.configured_db_config != new_db_config:
            config.error(
                "Cannot change c['db'] after the master has started",
            )

        return (yield super().reconfigServiceWithBuildbotConfig(new_config))

    @defer.inlineCallbacks
    def set_master(self, master):
        self._master = master
        self.model = model.Model(self)
        self.changes = changes.ChangesConnectorComponent(self)
        yield self.changes.setServiceParent(self)
        self.changesources = changesources.ChangeSourcesConnectorComponent(self)
        yield self.changesources.setServiceParent(self)
        self.schedulers = schedulers.SchedulersConnectorComponent(self)
        yield self.schedulers.setServiceParent(self)
        self.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self)
        yield self.sourcestamps.setServiceParent(self)
        self.buildsets = buildsets.BuildsetsConnectorComponent(self)
        yield self.buildsets.setServiceParent(self)
        self.buildrequests = buildrequests.BuildRequestsConnectorComponent(self)
        yield self.buildrequests.setServiceParent(self)
        self.state = state.StateConnectorComponent(self)
        yield self.state.setServiceParent(self)
        self.builds = builds.BuildsConnectorComponent(self)
        yield self.builds.setServiceParent(self)
        self.build_data = build_data.BuildDataConnectorComponent(self)
        yield self.build_data.setServiceParent(self)
        self.workers = workers.WorkersConnectorComponent(self)
        yield self.workers.setServiceParent(self)
        self.users = users.UsersConnectorComponent(self)
        yield self.users.setServiceParent(self)
        self.masters = masters.MastersConnectorComponent(self)
        yield self.masters.setServiceParent(self)
        self.builders = builders.BuildersConnectorComponent(self)
        yield self.builders.setServiceParent(self)
        self.projects = projects.ProjectsConnectorComponent(self)
        yield self.projects.setServiceParent(self)
        self.codebases = codebases.CodebasesConnectorComponent(self)
        yield self.codebases.setServiceParent(self)
        self.codebase_commits = codebase_commits.CodebaseCommitsConnectorComponent(self)
        yield self.codebase_commits.setServiceParent(self)
        self.codebase_branches = codebase_branches.CodebaseBranchConnectorComponent(self)
        yield self.codebase_branches.setServiceParent(self)
        self.steps = steps.StepsConnectorComponent(self)
        yield self.steps.setServiceParent(self)
        self.tags = tags.TagsConnectorComponent(self)
        yield self.tags.setServiceParent(self)
        self.logs = logs.LogsConnectorComponent(self)
        yield self.logs.setServiceParent(self)
        self.test_results = test_results.TestResultsConnectorComponent(self)
        yield self.test_results.setServiceParent(self)
        self.test_result_sets = test_result_sets.TestResultSetsConnectorComponent(self)
        yield self.test_result_sets.setServiceParent(self)

        self.cleanup_timer = internet.TimerService(self.CLEANUP_PERIOD, self._doCleanup)
        self.cleanup_timer.clock = self.master.reactor
        yield self.cleanup_timer.setServiceParent(self)

    @defer.inlineCallbacks
    def setup(self, check_version=True, verbose=True):
        if self.configured_db_config is None:
            self.configured_db_config = yield self.master.get_db_config(self.master.config)

        log.msg(
            f"Setting up database with URL {util.stripUrlPassword(self.configured_db_config.db_url)!r}"
        )

        # set up the engine and pool
        self._engine = enginestrategy.create_engine(
            self.configured_db_config.db_url,
            basedir=self.basedir,
            **self.configured_db_config.engine_kwargs,
        )
        self.upsert = get_upsert_method(self._engine)
        self.has_native_upsert = self.upsert != get_upsert_method(None)
        self.pool = pool.DBThreadPool(self._engine, reactor=self.master.reactor, verbose=verbose)
        self.pool.start()

        # make sure the db is up to date, unless specifically asked not to
        if check_version:
            if self.configured_db_config.db_url == 'sqlite://':
                # Using in-memory database. Since it is reset after each process
                # restart, `buildbot upgrade-master` cannot be used (data is not
                # persistent). Upgrade model here to allow startup to continue.
                yield self.model.upgrade()
            current = yield self.model.is_current()
            if not current:
                for l in upgrade_message.format(basedir=self.master.basedir).split('\n'):
                    log.msg(l)
                raise exceptions.DatabaseNotReadyError()

    @async_to_deferred
    async def _shutdown(self) -> None:
        """
        Called by stopService, except in test context
        as most tests don't call startService
        """
        await self._db_tasks_waiter.wait()

    @defer.inlineCallbacks
    def stopService(self):
        yield self._shutdown()
        try:
            yield super().stopService()
        finally:
            yield self.pool.stop()

    def _doCleanup(self):
        """
        Perform any periodic database cleanup tasks.

        @returns: Deferred
        """
        # pass on this if we're not configured yet
        if not self.configured_db_config:
            return None

        d = self.changes.pruneChanges(self.master.config.changeHorizon)
        d.addErrback(log.err, 'while pruning changes')
        return d

    def run_db_task(self, deferred_task: defer.Deferred) -> None:
        self._db_tasks_waiter.add(deferred_task)
