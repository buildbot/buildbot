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
from buildbot.test.fake import fakedb, fakemq

class FakeMaster(object):

    def __init__(self, basedir, db):
        self.basedir = basedir
        self.db = db
        self.caches = mock.Mock(name="caches")
        self.caches.get_cache = self.get_cache

    def addBuildset(self, scheduler, **kwargs):
        return self.db.buildsets.addBuildset(**kwargs)

    # caches

    def get_cache(self, cache_name, miss_fn):
        c = mock.Mock(name=cache_name)
        c.get = miss_fn
        return c

    # useful assertions


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
        pass

    def attachScheduler(self, scheduler, objectid):
        """Set up a scheduler with a fake master and db; sets self.sched, and
        sets the master's basedir to the absolute path of 'basedir' in the test
        directory.

        @returns: scheduler
        """
        scheduler.objectid = objectid

        # set up a fake master
        db = self.db = fakedb.FakeDBConnector(self)
        self.master = FakeMaster(os.path.abspath('basedir'), db)
        mq = self.mq = fakemq.FakeMQConnector(self.master, self)
        self.master.mq = mq
        scheduler.master = self.master

        db.insertTestData([
            fakedb.Object(id=objectid, name=scheduler.name,
                class_name='SomeScheduler'),
        ])

        self.sched = scheduler
        return scheduler

    class FakeChange:
        who = ''
        files = []
        comments = ''
        isdir=0
        links=None
        revision=None
        when=None
        branch=None
        category=None
        revlink=''
        properties={}
        repository=''
        project=''
        codebase=''

    def makeFakeChange(self, **kwargs):
        """Utility method to make a fake Change object with the given
        attributes"""
        ch = self.FakeChange()
        ch.__dict__.update(kwargs)
        return ch
