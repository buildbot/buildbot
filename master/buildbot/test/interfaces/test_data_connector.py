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
from buildbot.test.fake import fakemaster
from buildbot.test.util import interfaces
from buildbot.data import connector

class Tests(interfaces.InterfaceTests):

    def setUp(self):
        raise NotImplementedError

    def test_signature_get(self):
        @self.assertArgSpecMatches(self.data.get)
        def get(self, options, path):
            pass

    def test_signature_startConsuming(self):
        @self.assertArgSpecMatches(self.data.startConsuming)
        def startConsuming(self, callback, options, path):
            pass

    def test_signature_control(self):
        @self.assertArgSpecMatches(self.data.control)
        def control(self, action, args, path):
            pass

    def test_signature_updates_addChange(self):
        @self.assertArgSpecMatches(self.data.updates.addChange)
        def addChange(self, files=None, comments=None, author=None,
                revision=None, when_timestamp=None, branch=None, category=None,
                revlink='', properties={}, repository='', codebase=None,
                project='', src=None):
            pass


class TestFakeData(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                wantMq=True, wantData=True, wantDb=True)
        self.data = self.master.data


class TestDataConnector(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                wantMq=True)
        self.data = connector.DataConnector(self.master)
