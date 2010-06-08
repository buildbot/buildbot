from twisted.trial import unittest

from buildslave.commands import registry

class Registry(unittest.TestCase):

    def test_registerSlaveCommand(self):
        factory, version = lambda : None, "2.4"
        registry.registerSlaveCommand("nothing", factory, version)
        self.assertEqual(registry.commandRegistry['nothing'],
                    (factory, version))
