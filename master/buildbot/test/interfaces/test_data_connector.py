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
from buildbot.test.fake import fakemaster, fakedata, fakemq
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

    def test_signature_stopConsuming(self):
        cons = self.data.startConsuming(lambda : None, {}, ('change',))
        @self.assertArgSpecMatches(cons.stopConsuming)
        def stopConsuming(self):
            pass

    def test_signature_control(self):
        @self.assertArgSpecMatches(self.data.control)
        def control(self, action, args, path):
            pass


class RealTests(Tests):

    # tests that only "real" implementations will pass

    pass

class TestFakeData(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.master.mq = fakemq.FakeMQConnector(self.master)
        self.data = fakedata.FakeDataConnector(self.master)

class TestDataConnector(unittest.TestCase, RealTests):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.master.mq = fakemq.FakeMQConnector(self.master)
        self.data = connector.DataConnector(self.master)
