
from twisted.trial import unittest
from buildbot.status import master

from buildbot.test.util import steps
from buildbot.steps import artifact
from buildbot.test.fake import fakemaster, fakedb
import mock
from twisted.internet import defer, reactor
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

    def setupStep(self, step, sourcestampsInBuild=None, gotRevisionsInBuild=None, *args, **kwargs):
        sourcestamps = sourcestampsInBuild or []
        got_revisions = gotRevisionsInBuild or {}

        steps.BuildStepMixin.setupStep(self, step, *args, **kwargs)

        m = fakemaster.make_master()
        self.build.builder.botmaster = m.botmaster
        m.db = fakedb.FakeDBConnector(self)
        m.status = master.Status(m)
        m.config.buildbotURL = "baseurl/"

        if len(sourcestamps) < 1:
            ss = mock.Mock(name="sourcestamp")
            ss.sourcestampsetid = 0
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

        fake_br = fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0)
        fake_sset = fakedb.SourceStampSet(id=1)
        fake_buildset = fakedb.Buildset(id=1, sourcestampsetid=1, complete=1, results=0)
        fake_ss = fakedb.SourceStamp(id=1, branch='master', repository='https://url/project',
                                     codebase='c', revision='12', sourcestampsetid=1)

        self.build.builder.botmaster.parent.db.insertTestData([fake_br, fake_sset, fake_buildset, fake_ss])

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
        return self.runStep()