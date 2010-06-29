from twisted.trial import unittest

from buildslave.commands import registry
from buildslave.commands import shell

class Registry(unittest.TestCase):

    def test_getFactory(self):
        factory = registry.getFactory('shell')
        self.assertEqual(factory, shell.SlaveShellCommand)

    def test_getFactory_KeyError(self):
        self.assertRaises(KeyError, lambda : registry.getFactory('nosuchcommand'))

    def test_getAllCommandNames(self):
        self.failUnless('shell' in registry.getAllCommandNames())

    def test_all_commands_exist(self):
        # if this doesn't raise a KeyError, then we're good
        for n in registry.getAllCommandNames():
            registry.getFactory(n)
