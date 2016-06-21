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

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.schedulers import base
from buildbot.schedulers import manager


class SchedulerManager(unittest.TestCase):

    def setUp(self):
        self.next_objectid = 13
        self.objectids = {}

        self.master = mock.Mock()
        self.master.master = self.master

        def getObjectId(sched_name, class_name):
            k = (sched_name, class_name)
            try:
                rv = self.objectids[k]
            except KeyError:
                rv = self.objectids[k] = self.next_objectid
                self.next_objectid += 1
            return defer.succeed(rv)
        self.master.db.state.getObjectId = getObjectId

        def getScheduler(sched_id):
            return defer.succeed(dict(enabled=True))

        self.master.db.schedulers.getScheduler = getScheduler

        self.new_config = mock.Mock()

        self.sm = manager.SchedulerManager()
        self.sm.setServiceParent(self.master)
        return self.sm.startService()

    def tearDown(self):
        if self.sm.running:
            return self.sm.stopService()

    class Sched(base.BaseScheduler):

        # changing sch.attr should make a scheduler look "updated"
        compare_attrs = ('attr', )
        already_started = False
        reconfig_count = 0

        def startService(self):
            assert not self.already_started
            assert self.master is not None
            assert self.objectid is not None
            self.already_started = True
            return base.BaseScheduler.startService(self)

        def stopService(self):
            d = base.BaseScheduler.stopService(self)

            def still_set(_):
                assert self.master is not None
                assert self.objectid is not None
            d.addCallback(still_set)
            return d

        def __repr__(self):
            return "{}(attr={})".format(self.__class__.__name__, self.attr)

    class ReconfigSched(Sched):

        def reconfigServiceWithSibling(self, new_config):
            self.reconfig_count += 1
            self.attr = new_config.attr
            return base.BaseScheduler.reconfigServiceWithSibling(self, new_config)

    class ReconfigSched2(ReconfigSched):
        pass

    def makeSched(self, cls, name, attr='alpha'):
        sch = cls(name=name, builderNames=['x'], properties={})
        sch.attr = attr
        return sch

    # tests

    @defer.inlineCallbacks
    def test_reconfigService_add_and_change_and_remove(self):
        sch1 = self.makeSched(self.ReconfigSched, 'sch1', attr='alpha')
        self.new_config.schedulers = dict(sch1=sch1)

        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)
        self.assertEqual(sch1.reconfig_count, 1)

        sch1_new = self.makeSched(self.ReconfigSched, 'sch1', attr='beta')
        sch2 = self.makeSched(self.ReconfigSched, 'sch2', attr='alpha')
        self.new_config.schedulers = dict(sch1=sch1_new, sch2=sch2)

        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)

        # sch1 is still the active scheduler, and has been reconfig'd,
        # and has the correct attribute
        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)
        self.assertEqual(sch1.attr, 'beta')
        self.assertEqual(sch1.reconfig_count, 2)
        self.assertIdentical(sch1_new.parent, None)
        self.assertIdentical(sch1_new.master, None)

        self.assertIdentical(sch2.parent, self.sm)
        self.assertIdentical(sch2.master, self.master)

        self.new_config.schedulers = {}

        self.assertEqual(sch1.running, True)
        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)
        self.assertEqual(sch1.running, False)

    @defer.inlineCallbacks
    def test_reconfigService_class_name_change(self):
        sch1 = self.makeSched(self.ReconfigSched, 'sch1')
        self.new_config.schedulers = dict(sch1=sch1)

        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)
        self.assertEqual(sch1.reconfig_count, 1)

        sch1_new = self.makeSched(self.ReconfigSched2, 'sch1')
        self.new_config.schedulers = dict(sch1=sch1_new)

        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)

        # sch1 had its class name change, so sch1_new is now the active
        # instance
        self.assertIdentical(sch1_new.parent, self.sm)
        self.assertIdentical(sch1_new.master, self.master)

    @defer.inlineCallbacks
    def test_reconfigService_not_reconfigurable(self):
        sch1 = self.makeSched(self.Sched, 'sch1', attr='beta')
        self.new_config.schedulers = dict(sch1=sch1)

        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)

        sch1_new = self.makeSched(self.Sched, 'sch1', attr='alpha')
        self.new_config.schedulers = dict(sch1=sch1_new)

        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)

        # sch1 had parameter change but is not reconfigurable, so sch1_new is now the active
        # instance
        self.assertEqual(sch1_new.running, True)
        self.assertEqual(sch1.running, False)
        self.assertIdentical(sch1_new.parent, self.sm)
        self.assertIdentical(sch1_new.master, self.master)

    @defer.inlineCallbacks
    def test_reconfigService_not_reconfigurable_no_change(self):
        sch1 = self.makeSched(self.Sched, 'sch1', attr='beta')
        self.new_config.schedulers = dict(sch1=sch1)

        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)

        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)

        sch1_new = self.makeSched(self.Sched, 'sch1', attr='beta')
        self.new_config.schedulers = dict(sch1=sch1_new)

        yield self.sm.reconfigServiceWithBuildbotConfig(self.new_config)

        # sch1 had its class name change, so sch1_new is now the active
        # instance
        self.assertIdentical(sch1_new.parent, None)
        self.assertEqual(sch1_new.running, False)
        self.assertIdentical(sch1_new.master, None)
        self.assertEqual(sch1.running, True)
