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

from buildbot.test.fake import fakemaster, fakedb

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
        self.master = fakemaster.make_master(testcase=self,
                wantDb=True, wantMq=True, wantData=True)
        db = self.db = self.master.db
        self.mq = self.master.mq
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
