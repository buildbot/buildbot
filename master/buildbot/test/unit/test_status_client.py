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

from buildbot import interfaces
from buildbot.status import client
from buildbot.test.util import logging
from twisted.trial import unittest


class TestPBListener(logging.LoggingMixin, unittest.TestCase):

    def setUp(self):
        self.setUpLogging()

    def test_PBListener_logs(self):
        client.PBListener(9989)
        self.assertLogged('PBListener.*unused')

    def test_PBListener_IStatusListener(self):
        pbl = client.PBListener(9989)
        self.failUnless(interfaces.IStatusReceiver.providedBy(pbl))
