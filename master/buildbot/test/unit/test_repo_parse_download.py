from twisted.trial import unittest

from buildbot.steps.source import Repo

class RepoURL(unittest.TestCase):

    def test_parse1(self):
        r = Repo()
        self.assertEqual(r.parseDownloadProperty("repo download test/bla 564/12"),["test/bla 564/12"])
    def test_parse2(self):
        r = Repo()
        self.assertEqual(r.parseDownloadProperty("repo download test/bla 564/12 repo download test/bla 564/2"),["test/bla 564/12","test/bla 564/2"])
    def test_parse3(self):
        r = Repo()
        self.assertEqual(r.parseDownloadProperty("repo download test/bla 564/12 repo download test/bla 564/2 test/foo 5/1"),["test/bla 564/12","test/bla 564/2","test/foo 5/1"])
        self.assertEqual(r.parseDownloadProperty("repo download test/bla 564/12"),["test/bla 564/12"])
