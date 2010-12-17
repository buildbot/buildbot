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

from mock import Mock

from buildbot.process.properties import Properties
from buildbot.steps.slave import SetPropertiesFromEnv

class TestSetPropertiesFromEnv(unittest.TestCase):
    def testBasic(self):
        s = SetPropertiesFromEnv(variables = ["one", "two", "three", "five", "six"], source = "me")
        s.build = Mock()
        s.build.getProperties.return_value = props = Properties()
        s.buildslave = Mock()
        s.buildslave.slave_environ = { "one": 1, "two": None, "six": 6 }
        props.setProperty("four", 4, "them")
        props.setProperty("five", 5, "them")
        props.setProperty("six", 99, "them")

        s.step_status = Mock()
        s.deferred = Mock()

        s.start()

        self.failUnlessEqual(props.getProperty('one'), 1)
        self.failUnlessEqual(props.getPropertySource('one'), 'me')
        self.failUnlessEqual(props.getProperty('two'), None)
        self.failUnlessEqual(props.getProperty('three'), None)
        self.failUnlessEqual(props.getProperty('four'), 4)
        self.failUnlessEqual(props.getPropertySource('four'), 'them')
        self.failUnlessEqual(props.getProperty('five'), 5)
        self.failUnlessEqual(props.getPropertySource('five'), 'them')
        self.failUnlessEqual(props.getProperty('six'), 6)
        self.failUnlessEqual(props.getPropertySource('six'), 'me')
