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

import mock
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.schedulers import manager, base

class SchedulerManager(unittest.TestCase):

    def setUp(self):
        self.next_schedulerid = 13
        self.schedulerids = {}

        self.master = mock.Mock()
        def getSchedulerId(sched_name, class_name):
            k = (sched_name, class_name)
            try:
                rv = self.schedulerids[k]
            except:
                rv = self.schedulerids[k] = self.next_schedulerid
                self.next_schedulerid += 1
            return defer.succeed(rv)
        self.master.db.schedulers.getSchedulerId = getSchedulerId

        self.sm = manager.SchedulerManager(self.master)
        self.sm.startService()

    def tearDown(self):
        if self.sm.running:
            return self.sm.stopService()

    class Sched(base.BaseScheduler):

        # changing sch.attr should make a scheduler look "updated"
        compare_attrs = base.BaseScheduler.compare_attrs + ( 'attr', )
        already_started = False

        def startService(self):
            assert not self.already_started
            assert self.master is not None
            assert self.schedulerid is not None
            self.already_started = True
            base.BaseScheduler.startService(self)

        def stopService(self):
            d = base.BaseScheduler.stopService(self)
            def still_set(_):
                assert self.master is not None
                assert self.schedulerid is not None
            d.addCallback(still_set)
            return d

        def assertNotSet(self):
            assert not self.master
            assert self.schedulerid is None

    def makeSched(self, name, attr='alpha'):
        sch = self.Sched(name=name, builderNames=['x'], properties={})
        sch.attr = attr
        return sch

    # tests

    def test_updateSchedulers(self):
        d = defer.succeed(None)

        # add a scheduler
        fred1 = self.makeSched('fred', attr='alpha')
        d.addCallback(lambda _ : self.sm.updateSchedulers([ fred1 ]))
        def check1(_):
            self.assertEqual(fred1.parent, self.sm)
        d.addCallback(check1)

        # update it with an identically-configured scheduler and a new one
        fred2 = self.makeSched('fred', attr='alpha')
        ginger1 = self.makeSched('ginger')
        d.addCallback(lambda _ : self.sm.updateSchedulers([ fred2, ginger1 ]))
        def check2(_):
            # fred1 is still active, and fred2 is not.  Ginger is active
            self.assertEqual(fred1.parent, self.sm)
            self.assertEqual(fred2.parent, None)
            self.assertEqual(ginger1.parent, self.sm)
        d.addCallback(check2)

        # update it with an differently-configured fred; same ginger
        fred3 = self.makeSched('fred', attr='beta')
        ginger2 = self.makeSched('ginger')
        d.addCallback(lambda _ : self.sm.updateSchedulers([ ginger2, fred3 ]))
        def check3(_):
            # fred1 is inactive and fred3 is active
            self.assertEqual(fred1.parent, None)
            self.assertEqual(fred3.parent, self.sm)
            self.assertEqual(ginger1.parent, self.sm)
            self.assertEqual(ginger2.parent, None)
        d.addCallback(check3)

        # and finally, remove fred
        d.addCallback(lambda _ : self.sm.updateSchedulers([ ginger2 ]))
        def check4(_):
            self.assertEqual(fred3.parent, None)
            self.assertEqual(ginger1.parent, self.sm)
            self.assertEqual(ginger2.parent, None)
        d.addCallback(check4)

        return d
