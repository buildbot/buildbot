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

class KeyedSets(unittest.TestCase):

    def setUp(self):
        self.ks = collections.KeyedSets()

    def test_getitem_default(self):
        self.assertEqual(self.ks['x'], set())
        # remaining tests effectively cover __getitem__

    def test_add(self):
        self.ks.add('y', 2)
        self.assertEqual(self.ks['y'], set([2]))

    def test_add_twice(self):
        self.ks.add('z', 2)
        self.ks.add('z', 4)
        self.assertEqual(self.ks['z'], set([2, 4]))

    def test_discard_noError(self):
        self.ks.add('full', 12)
        self.ks.discard('empty', 13) # should not fail
        self.ks.discard('full', 13) # nor this
        self.assertEqual(self.ks['full'], set([12]))

    def test_discard_existing(self):
        self.ks.add('yarn', 'red')
        self.ks.discard('yarn', 'red')
        self.assertEqual(self.ks['yarn'], set([]))

    def test_contains_true(self):
        self.ks.add('yarn', 'red')
        self.assertTrue('yarn' in self.ks)

    def test_contains_false(self):
        self.assertFalse('yarn' in self.ks)

    def test_contains_setNamesNotContents(self):
        self.ks.add('yarn', 'red')
        self.assertFalse('red' in self.ks)

    def test_pop_exists(self):
        self.ks.add('names', 'pop')
        self.ks.add('names', 'coke')
        self.ks.add('names', 'soda')
        popped = self.ks.pop('names')
        remaining = self.ks['names']
        self.assertEqual((popped, remaining),
                         (set(['pop', 'coke', 'soda']), set()))

    def test_pop_missing(self):
        self.assertEqual(self.ks.pop('flavors'), set())
