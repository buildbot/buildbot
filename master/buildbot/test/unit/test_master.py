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
import shutil
import mock
from twisted.trial import unittest
from buildbot import master

class TestBuildMaster(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath('basedir')
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)
        self.master = master.BuildMaster(self.basedir)

    def tearDown(self):
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def test_change_subscription(self):
        self.newchange = mock.Mock()
        self.master.db = mock.Mock()
        self.master.db.changes.addChange.return_value = self.newchange

        self.got_change = None
        def sub(change):
            self.got_change = change
        self.master.subscribeToChanges(sub)

        d = self.master.addChange(this='chdict')
        def check(change):
            self.failUnless(change is self.newchange) # addChange return value
            self.failUnless(self.got_change is self.newchange) # subscription
        d.addCallback(check)
        return d
