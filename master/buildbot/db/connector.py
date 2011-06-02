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

from twisted.python import log
from twisted.application import internet, service
from buildbot.db import enginestrategy

from buildbot.db import pool, model, changes, schedulers, sourcestamps
from buildbot.db import state, buildsets, buildrequests, builds

class DBConnector(service.MultiService):
    """
    The connection between Buildbot and its backend database.  This is
    generally accessible as master.db, but is also used during upgrades.

    Most of the interesting operations available via the connector are
    implemented in connector components, available as attributes of this
    object, and listed below.
    """

    # Period, in seconds, of the cleanup task.  This master will perform
    # periodic cleanup actions on this schedule.
    CLEANUP_PERIOD = 3600

    def __init__(self, master, db_url, basedir):
        service.MultiService.__init__(self)
        self.master = master
        self.basedir = basedir

        self._engine = enginestrategy.create_engine(db_url, basedir=self.basedir)
        self.pool = pool.DBThreadPool(self._engine)

        # set up components
        self.model = model.Model(self)
        self.changes = changes.ChangesConnectorComponent(self)
        self.schedulers = schedulers.SchedulersConnectorComponent(self)
        self.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self)
        self.buildsets = buildsets.BuildsetsConnectorComponent(self)
        self.buildrequests = buildrequests.BuildRequestsConnectorComponent(self)
        self.state = state.StateConnectorComponent(self)
        self.builds = builds.BuildsConnectorComponent(self)

        self.cleanup_timer = internet.TimerService(self.CLEANUP_PERIOD, self.doCleanup)
        self.cleanup_timer.setServiceParent(self)

        self.changeHorizon = None # default value; set by master

    def doCleanup(self):
        """
        Perform any periodic database cleanup tasks.

        @returns: Deferred
        """
        d = self.changes.pruneChanges(self.master.config.changeHorizon)
        d.addErrback(log.err, 'while pruning changes')
        return d
