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


from twisted.trial import unittest

from buildbot.schedulers import basic

class FakeDBConnector(object):
    pass

class FakeSchedulerManager(object):
    def __init__(self):
        self.db = FakeDBConnector()

class Scheduler(unittest.TestCase):

    def makeScheduler(self, **kwargs):
        """Set up a new scheduler with a fake environment; also adds default
        constructor args for convenience"""
        defaultargs = dict(
                name="tsched",
                branch=None,
                treeStableTimer=60,
                builderNames=['tbuild'])
        defaultargs.update(kwargs)
        sch = basic.Scheduler(**defaultargs)

        # NOTE: this doesn't actually call setServiceParent or start()
        sch.parent = FakeSchedulerManager()
        return sch

    def test_constructor_simple(self):
        sch = basic.Scheduler(
                name="tsched",
                branch=None,
                treeStableTimer=60,
                builderNames=['tbuild'])
        self.assertEqual(sch.name, "tsched")
