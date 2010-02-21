from twisted.trial import unittest

from buildbot.util import collections

class defaultdict(unittest.TestCase):

    # minimal tests here, since this is usually available from Python

    def setUp(self):
        self.dd = collections.defaultdict(list)
    
    def test_getitem_default(self):
        self.assertEqual(self.dd['x'], [])

    def test_getitem_existing(self):
        self.dd['y'] = 13
        self.assertEqual(self.dd['y'], 13)

class DictOfSets(unittest.TestCase):

    def setUp(self):
        self.dos = collections.DictOfSets()

    def test_getitem_default(self):
        self.assertEqual(self.dos['x'], set())

    def test_getitem_exists(self):
        self.dos.add('y', 2)
        self.assertEqual(self.dos['y'], set([2]))
