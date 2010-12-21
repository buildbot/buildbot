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
from buildbot.changes import manager, base

class TestChangeManager(unittest.TestCase):
    def setUp(self):
        self.cm = manager.ChangeManager()
        self.cm.parent = mock.Mock()
        self.cm.startService()

    def tearDown(self):
        return self.cm.stopService()

    def test_addSource_removeSource(self):
        class MySource(base.ChangeSource):
            pass

        src = MySource()
        self.cm.addSource(src)

        # addSource should set the source's 'master'
        assert src.master is self.cm.parent

        d = self.cm.removeSource(src)
        def check(_):
            # and removeSource should rmeove it.
            assert src.master is None
        return d
