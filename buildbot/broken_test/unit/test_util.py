# -*- test-case-name: buildbot.broken_test.test_util -*-

from twisted.trial import unittest

from buildbot import util


class Foo(util.ComparableMixin):
    compare_attrs = ["a", "b"]

    def __init__(self, a, b, c):
        self.a, self.b, self.c = a,b,c


class Bar(Foo, util.ComparableMixin):
    compare_attrs = ["b", "c"]

class Compare(unittest.TestCase):
    def testCompare(self):
        f1 = Foo(1, 2, 3)
        f2 = Foo(1, 2, 4)
        f3 = Foo(1, 3, 4)
        b1 = Bar(1, 2, 3)
        self.failUnless(f1 == f2)
        self.failIf(f1 == f3)
        self.failIf(f1 == b1)

class test_checkRepoURL(unittest.TestCase):
    def assertUrl(self, real_url, expected_url):
        new_url = util.remove_userpassword(real_url)
        self.assertEqual(expected_url, new_url)

    def test_url_with_no_user_and_password(self):
        self.assertUrl('http://myurl.com/myrepo', 'http://myurl.com/myrepo')

    def test_url_with_user_and_password(self):
        self.assertUrl('http://myuser:mypass@myurl.com/myrepo', 'http://myurl.com/myrepo')

    def test_another_url_with_no_user_and_password(self):
        self.assertUrl('http://myurl2.com/myrepo2', 'http://myurl2.com/myrepo2')

    def test_another_url_with_user_and_password(self):
        self.assertUrl('http://myuser2:mypass2@myurl2.com/myrepo2', 'http://myurl2.com/myrepo2')

    def test_with_different_protocol_without_user_and_password(self):
        self.assertUrl('ssh://myurl3.com/myrepo3', 'ssh://myurl3.com/myrepo3')

    def test_with_different_protocol_with_user_and_password(self):
        self.assertUrl('ssh://myuser3:mypass3@myurl3.com/myrepo3', 'ssh://myurl3.com/myrepo3')

    def test_file_path(self):
        self.assertUrl('/home/me/repos/my-repo', '/home/me/repos/my-repo')

    def test_win32file_path(self):
        self.assertUrl('c:\\repos\\my-repo', 'c:\\repos\\my-repo')

class DictStuff(unittest.TestCase):
    def test_dictofsets(self):
        d = util.DictOfSets()
        d.add("a", 1)
        d.add("a", 2)
        d.add("b", 3)
        self.failUnless("a" in d)
        self.failUnless("b" in d)
        self.failIf("c" in d)
        self.failUnlessEqual(d["a"], set([1,2]))
        self.failUnlessEqual(d["b"], set([3]))
        self.failUnlessRaises(KeyError, lambda: d["c"])
        d.remove("c", 4) # ignored
        d.remove("b", 4) # ignored
        d.remove("b", 3)
        self.failIf("b" in d)
        self.failUnlessEqual(d.pop("a"), set([1,2]))
        self.failIf("a" in d)
        self.failUnlessEqual(d.pop("c"), set())
        self.failUnlessEqual(d.pop("f"), set())
