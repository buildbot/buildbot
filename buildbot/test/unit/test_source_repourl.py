from twisted.trial import unittest

from buildbot.steps.source import Source

class SourceStamp(object):
    repository = "test"

class Build(object):
    s = SourceStamp()
    def getSourceStamp(self):
        return self.s

class RepoURL(unittest.TestCase):

    def test_backward_compatibility(self):
        s = Source()
        s.build = Build()
        self.assertEqual(s.computeRepositoryURL("repourl"), "repourl")

    def test_format_string(self):
        s = Source()
        s.build = Build()
        self.assertEquals(s.computeRepositoryURL("http://server/%s"), "http://server/test")

    def test_dict(self):
        s = Source()
        s.build = Build()
        dict = {}
        dict['test'] = "ssh://server/testrepository"
        self.assertEquals(s.computeRepositoryURL(dict), "ssh://server/testrepository")

    def test_callable(self):
        s = Source()
        s.build = Build()
        func = lambda x: x[::-1]
        self.assertEquals(s.computeRepositoryURL(func), "tset")

