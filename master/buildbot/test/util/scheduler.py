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

import os
import mock
from buildbot.test.fake import fakedb

class FakeMaster(object):

    def __init__(self, basedir, db):
        self.basedir = basedir
        self.db = db
        self.changes_subscr_cb = None
        self.bset_subscr_cb = None
        self.bset_completion_subscr_cb = None
        self.caches = mock.Mock(name="caches")
        self.caches.get_cache = self.get_cache

    def addBuildset(self, **kwargs):
        return self.db.buildsets.addBuildset(**kwargs)

    # subscriptions
    # note that only one subscription of each type is supported

    def _makeSubscription(self, attr_to_clear):
        sub = mock.Mock()
        def unsub():
            setattr(self, attr_to_clear, None)
        sub.unsubscribe = unsub
        return sub

    def subscribeToChanges(self, callback):
        assert not self.changes_subscr_cb
        self.changes_subscr_cb = callback
        return self._makeSubscription('changes_subscr_cb')

    def subscribeToBuildsets(self, callback):
        assert not self.bset_subscr_cb
        self.bset_subscr_cb = callback
        return self._makeSubscription('bset_subscr_cb')

    def subscribeToBuildsetCompletions(self, callback):
        assert not self.bset_completion_subscr_cb
        self.bset_completion_subscr_cb = callback
        return self._makeSubscription('bset_completion_subscr_cb')

    # caches

    def get_cache(self, cache_name, miss_fn):
        c = mock.Mock(name=cache_name)
        c.get = miss_fn
        return c

    # useful assertions

    def getSubscriptionCallbacks(self):
        """get the subscription callbacks set on the master, in a dictionary
        with keys @{buildsets}, @{buildset_completion}, and C{changes}."""
        return dict(buildsets=self.bset_subscr_cb,
                    buildset_completion=self.bset_completion_subscr_cb,
                    changes=self.changes_subscr_cb)


class SchedulerMixin(object):
    """
    This class fakes out enough of a master and the various relevant database
    connectors to test schedulers.  All of the database methods have identical
    signatures to the real database connectors, but for ease of testing always
    return an already-fired Deferred, meaning that there is no need to wait for
    events to complete.

    This class is tightly coupled with the various L{buildbot.test.fake.fakedb}
    module.  All instance variables are only available after C{attachScheduler}
    has been called.

    @ivar sched: scheduler instance
    @ivar master: the fake master
    @ivar db: the fake db (same as C{self.master.db}, but shorter)
    """

    def setUpScheduler(self):
        pass

    def tearDownScheduler(self):
        # TODO: break some reference cycles
        pass

    def attachScheduler(self, scheduler, schedulerid):
        """Set up a scheduler with a fake master and db; sets self.sched, and
        sets the master's basedir to the absolute path of 'basedir' in the test
        directory.

        @returns: scheduler
        """
        scheduler.schedulerid = schedulerid

        # set up a fake master
        db = self.db = fakedb.FakeDBConnector(self)
        self.master = FakeMaster(os.path.abspath('basedir'), db)
        scheduler.master = self.master

        self.sched = scheduler
        return scheduler

    class FakeChange: pass
    def makeFakeChange(self, **kwargs):
        """Utility method to make a fake Change object with the given
        attributes"""
        ch = self.FakeChange()
        ch.__dict__.update(kwargs)
        return ch
