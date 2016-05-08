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

from buildbot.changes import manager
from buildbot.test.fake import fakemaster
from buildbot.util import service


class FakeChangeSource(service.ClusteredBuildbotService):
    pass


class TestChangeManager(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.cm = manager.ChangeManager()
        self.cm.setServiceParent(self.master)
        self.new_config = mock.Mock()

    def make_sources(self, n):
        for i in range(n):
            src = FakeChangeSource(name='ChangeSource %d' % i)
            yield src

    def test_reconfigService_add(self):
        src1, src2 = self.make_sources(2)
        src1.setServiceParent(self.cm)
        self.new_config.change_sources = [src1, src2]

        d = self.cm.reconfigServiceWithBuildbotConfig(self.new_config)

        @d.addCallback
        def check(_):
            self.assertIdentical(src2.parent, self.cm)
            self.assertIdentical(src2.master, self.master)
        return d

    def test_reconfigService_remove(self):
        src1, = self.make_sources(1)
        src1.setServiceParent(self.cm)
        self.new_config.change_sources = []

        d = self.cm.reconfigServiceWithBuildbotConfig(self.new_config)

        @d.addCallback
        def check(_):
            self.assertIdentical(src1.parent, None)
            self.assertIdentical(src1.master, None)
        return d
