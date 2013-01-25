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
from twisted.internet import defer
from twisted.python import log
from twisted.application import internet, service
from buildbot import config
from buildbot.db import enginestrategy
from buildbot.db import pool, model, changes, schedulers, sourcestamps, sourcestampsets
from buildbot.db import state, buildsets, buildrequests, builds, users

class DatabaseNotReadyError(Exception):
    pass

upgrade_message = textwrap.dedent("""\

    The Buildmaster database needs to be upgraded before this version of
    buildbot can run.  Use the following command-line

        buildbot upgrade-master path/to/master

    to upgrade the database, and try starting the buildmaster again.  You may
    want to make a backup of your buildmaster before doing so.
    """).strip()

class DBConnector(config.ReconfigurableServiceMixin, service.MultiService):
    # The connection between Buildbot and its backend database.  This is
    # generally accessible as master.db, but is also used during upgrades.
    #
    # Most of the interesting operations available via the connector are
    # implemented in connector components, available as attributes of this
    # object, and listed below.

    # Period, in seconds, of the cleanup task.  This master will perform
    # periodic cleanup actions on this schedule.
    CLEANUP_PERIOD = 3600

    def __init__(self, master, basedir):
        service.MultiService.__init__(self)
        self.setName('db')
        self.master = master
        self.basedir = basedir

        # not configured yet - we don't build an engine until the first
        # reconfig
        self.configured_url = None

        # set up components
        self._engine = None # set up in reconfigService
        self.pool = None # set up in reconfigService
        self.model = model.Model(self)
        self.changes = changes.ChangesConnectorComponent(self)
        self.schedulers = schedulers.SchedulersConnectorComponent(self)
        self.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self)
        self.sourcestampsets = sourcestampsets.SourceStampSetsConnectorComponent(self)
        self.buildsets = buildsets.BuildsetsConnectorComponent(self)
        self.buildrequests = buildrequests.BuildRequestsConnectorComponent(self)
        self.state = state.StateConnectorComponent(self)
        self.builds = builds.BuildsConnectorComponent(self)
        self.users = users.UsersConnectorComponent(self)

        self.cleanup_timer = internet.TimerService(self.CLEANUP_PERIOD,
                self._doCleanup)
        self.cleanup_timer.setServiceParent(self)


    def setup(self, check_version=True, verbose=True):
        db_url = self.configured_url = self.master.config.db['db_url']

        log.msg("Setting up database with URL %r" % (db_url,))

        # set up the engine and pool
        self._engine = enginestrategy.create_engine(db_url,
                                basedir=self.basedir)
        self.pool = pool.DBThreadPool(self._engine, verbose=verbose)

        # make sure the db is up to date, unless specifically asked not to
        if check_version:
            d = self.model.is_current()
            def check_current(res):
                if not res:
                    for l in upgrade_message.split('\n'):
                        log.msg(l)
                    raise DatabaseNotReadyError()
            d.addCallback(check_current)
        else:
            d = defer.succeed(None)

        return d


    def reconfigService(self, new_config):
        # double-check -- the master ensures this in config checks
        assert self.configured_url == new_config.db['db_url']

        return config.ReconfigurableServiceMixin.reconfigService(self,
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
