
from twisted.trial import unittest
from buildbot.status import master

from buildbot.test.util import steps
from buildbot.steps import artifact
from buildbot.test.fake import fakemaster, fakedb
from buildbot.status.results import SUCCESS

class FakeSourceStamp(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def asDict(self, includePatch = True):
        return self.__dict__.copy()

class TestFindPreviousSuccessfulBuild(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def setupStep(self, step, sourcestampsInBuild=None, *args, **kwargs):
        sourcestamps = sourcestampsInBuild or []
        got_revisions = {}

        steps.BuildStepMixin.setupStep(self, step, *args, **kwargs)

        m = fakemaster.make_master()
        self.build.builder.botmaster = m.botmaster
        m.db = fakedb.FakeDBConnector(self)
        m.status = master.Status(m)
        m.config.buildbotURL = "baseurl/"
        m.db.mastersconfig.setupMaster()

        if len(sourcestamps) < 1:
            ss = FakeSourceStamp(codebase='c',
                                 repository='https://url/project',
                                 branch='mybranch',
                                 revision=3,
                                 sourcestampsetid=3)
            sourcestamps.append(ss)

        def getAllSourceStamps():
            return sourcestamps
        self.build.getAllSourceStamps = getAllSourceStamps
        self.build.build_status.getSourceStamps = getAllSourceStamps

        def getAllGotRevisions():
            return got_revisions
        self.build.build_status.getAllGotRevisions = getAllGotRevisions

        self.build.requests = []
        self.build.builder.config.name = "A"

        self.build.builder.builder_status.getFriendlyName = lambda: "A"

        def addURL(name, url, results=None):
            self.step_status.urls[name] = url
            if results is not None:
                self.step_status.urls[name] = {'url': url, 'results': results}

        self.step_status.addURL = addURL

        fake_br = fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0)
        fake_ss = fakedb.SourceStamp(id=1, branch='master', repository='https://url/project',
                                     codebase='c', revision='12', sourcestampsetid=1)
        fake_build = fakedb.Build(id=1, number=1, brid=1)

        m.db.insertTestData([fake_br, fake_ss, fake_build])
        m.db.buildrequests.setRelatedSourcestamps(1, [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=1)])

    # tests

    def test_previous_build_not_found(self):
        self.setupStep(artifact.FindPreviousSuccessfulBuild())
        self.expectOutcome(result=SUCCESS, status_text=['Running build (previous sucessful build not found).'])
        return self.runStep()

    # check build url
    def test_previous_build_found(self):
        self.setupStep(artifact.FindPreviousSuccessfulBuild(),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)])


        self.expectOutcome(result=SUCCESS, status_text=['Found previous successful build.'])
        self.expectURLS({'A #1': 'baseurl/builders/A/builds/1'})
        return self.runStep()
