from twisted.trial import unittest

from mock import Mock

from buildbot.process.properties import Properties
from buildbot.steps.master import SetPropertiesFromEnv

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
