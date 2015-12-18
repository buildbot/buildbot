# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members
from future.utils import iteritems

from buildbot.reporters import utils
from buildbot.reporters.gerrit import GERRIT_LABEL_REVIEWED
from buildbot.reporters.gerrit import GERRIT_LABEL_VERIFIED
from buildbot.reporters.gerrit import GerritStatusPush
from buildbot.reporters.gerrit import defaultReviewCB
from buildbot.reporters.gerrit import defaultSummaryCB
from buildbot.reporters.gerrit import makeReviewResult
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from mock import Mock
from mock import call
from twisted.internet import defer
from twisted.trial import unittest


import warnings
warnings.filterwarnings('error', message='.*Gerrit status')


def testReviewCB(builderName, build, result, status, arg):
    verified = 1 if result == SUCCESS else -1
    return makeReviewResult(str({'name': builderName, 'result': result}),
                            (GERRIT_LABEL_VERIFIED, verified))


def testStartCB(builderName, build, arg):
    return makeReviewResult(str({'name': builderName}),
                            (GERRIT_LABEL_REVIEWED, 0))


def testSummaryCB(buildInfoList, results, status, arg):
    success = False
    failure = False

    for buildInfo in buildInfoList:
        if buildInfo['result'] == SUCCESS:
            success = True
        else:
            failure = True

    if failure:
        verified = -1
    elif success:
        verified = 1
    else:
        verified = 0

    return makeReviewResult(str(buildInfoList),
                            (GERRIT_LABEL_VERIFIED, verified))


def legacyTestReviewCB(builderName, build, result, status, arg):
    msg = str({'name': builderName, 'result': result})
    return (msg, 1 if result == SUCCESS else -1, 0)


def legacyTestSummaryCB(buildInfoList, results, status, arg):
    success = False
    failure = False

    for buildInfo in buildInfoList:
        if buildInfo['result'] == SUCCESS:
            success = True
        else:
            failure = True

    if failure:
        verified = -1
    elif success:
        verified = 1
    else:
        verified = 0

    return (str(buildInfoList), verified, 0)


class TestGerritStatusPush(unittest.TestCase):

    TEST_PROJECT = u'testProject'
    TEST_REVISION = u'd34db33fd43db33f'
    TEST_CHANGE_ID = u'I5bdc2e500d00607af53f0fa4df661aada17f81fc'
    TEST_BUILDER_NAME = u'Builder0'
    TEST_PROPS = {
        'gerrit_branch': 'refs/changes/34/1234/1',
        'project': TEST_PROJECT,
        'got_revision': TEST_REVISION,
        'revision': TEST_REVISION,
        'event.change.id': TEST_CHANGE_ID,
        'event.change.project': TEST_PROJECT,
    }
    THING_URL = 'http://thing.example.com'

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def setupGerritStatusPushSimple(self, *args, **kwargs):
        serv = kwargs.pop("server", "serv")
        username = kwargs.pop("username", "user")
        gsp = GerritStatusPush(serv, username, *args, **kwargs)
        yield gsp.setServiceParent(self.master)
        yield gsp.startService()
        defer.returnValue(gsp)

    @defer.inlineCallbacks
    def setupGerritStatusPush(self, *args, **kwargs):
        gsp = yield self.setupGerritStatusPushSimple(*args, **kwargs)
        gsp.sendCodeReview = Mock()
        defer.returnValue(gsp)

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults, finalResult):
        # this testsuite always goes through setupBuildResults so that
        # the data is sure to be the real data schema known coming from data api

        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Buildslave(id=13, name='sl'),
            fakedb.Builder(id=79, name='Builder0'),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.Buildset(id=98, results=finalResult, reason="testReason1"),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.SourceStamp(id=234),
            fakedb.Change(changeid=13, branch=u'master', revision=u'9283', author='me@foo',
                          repository=u'https://...', codebase=u'cbgerrit',
                          project=u'world-domination', sourcestampid=234),
        ])
        i = 0
        for results in buildResults:
            self.db.insertTestData([
                fakedb.BuildRequest(id=11 + i, buildsetid=98, builderid=79 + i),
                fakedb.Build(id=20 + i, number=i, builderid=79 + i, buildrequestid=11 + i, buildslaveid=13,
                             masterid=92, results=results, state_string=u"buildText"),
                fakedb.Step(id=50 + i, buildid=20 + i, number=5, name='make'),
                fakedb.Log(id=60 + i, stepid=50 + i, name='stdio', slug='stdio', type='s',
                           num_lines=7),
                fakedb.LogChunk(logid=60 + i, first_line=0, last_line=1, compressed=0,
                                content=u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).'),
                fakedb.BuildProperty(buildid=20 + i, name="slavename", value="sl"),
                fakedb.BuildProperty(buildid=20 + i, name="reason", value="because"),
            ])
            for k, v in iteritems(self.TEST_PROPS):
                self.db.insertTestData([
                    fakedb.BuildProperty(buildid=20 + i, name=k, value=v)
                    ])
            i += 1
        res = yield utils.getDetailsForBuildset(self.master, 98, wantProperties=True)
        builds = res['builds']
        buildset = res['buildset']

        @defer.inlineCallbacks
        def getChangesForBuild(buildid):
            assert buildid == 20
            ch = yield self.master.db.changes.getChange(13)
            defer.returnValue([ch])

        self.master.db.changes.getChangesForBuild = getChangesForBuild
        defer.returnValue((buildset, builds))

    def makeBuildInfo(self, buildResults, resultText):
        info = []
        for i in xrange(len(buildResults)):
            info.append({'name': u"Builder%d" % i, 'result': buildResults[i],
                         'resultText': resultText[i], 'text': u'buildText',
                         'url': "http://localhost:8080/#builders/%d/builds/%d" % (79 + i, i)})
        return info

    @defer.inlineCallbacks
    def run_fake_summary_build(self, gsp, buildResults, finalResult,
                               resultText, expWarning=False):
        buildset, builds = yield self.setupBuildResults(buildResults, finalResult)
        yield gsp.buildsetComplete('buildset.98.complete'.split("."),
                                   buildset)

        info = self.makeBuildInfo(buildResults, resultText)
        if expWarning:
            self.assertEqual([w['message'] for w in self.flushWarnings()],
                             ['The Gerrit status callback uses the old '
                              'way to communicate results.  The outcome '
                              'might be not what is expected.'])
        defer.returnValue(str(info))

    # check_summary_build and check_summary_build_legacy differ in two things:
    #   * the callback used
    #   * the expected result

    @defer.inlineCallbacks
    def check_summary_build(self, buildResults, finalResult, resultText,
                            verifiedScore):
        gsp = yield self.setupGerritStatusPush(summaryCB=testSummaryCB)

        msg = yield self.run_fake_summary_build(gsp, buildResults, finalResult,
                                                resultText)

        result = makeReviewResult(msg,
                                  (GERRIT_LABEL_VERIFIED, verifiedScore))
        gsp.sendCodeReview.assert_called_once_with(self.TEST_PROJECT,
                                                   self.TEST_REVISION,
                                                   result)

    @defer.inlineCallbacks
    def check_summary_build_legacy(self, buildResults, finalResult, resultText,
                                   verifiedScore):
        gsp = yield self.setupGerritStatusPush(summaryCB=legacyTestSummaryCB)

        msg = yield self.run_fake_summary_build(gsp, buildResults, finalResult,
                                                resultText, expWarning=True)

        result = makeReviewResult(msg,
                                  (GERRIT_LABEL_VERIFIED, verifiedScore),
                                  (GERRIT_LABEL_REVIEWED, 0))
        gsp.sendCodeReview.assert_called_once_with(self.TEST_PROJECT,
                                                   self.TEST_REVISION,
                                                   result)

    @defer.inlineCallbacks
    def test_gerrit_ssh_cmd(self):
        kwargs = {
            'server': 'example.com',
            'username': 'buildbot',
        }
        without_identity = yield self.setupGerritStatusPush(**kwargs)

        expected1 = ['ssh', 'buildbot@example.com', '-p', '29418', 'gerrit', 'foo']
        self.assertEqual(expected1, without_identity._gerritCmd('foo'))
        yield without_identity.disownServiceParent()
        with_identity = yield self.setupGerritStatusPush(
            identity_file='/path/to/id_rsa', **kwargs)
        expected2 = [
            'ssh', '-i', '/path/to/id_rsa', 'buildbot@example.com', '-p', '29418',
            'gerrit', 'foo',
        ]
        self.assertEqual(expected2, with_identity._gerritCmd('foo'))

    def test_buildsetComplete_success_sends_summary_review(self):
        d = self.check_summary_build(buildResults=[SUCCESS, SUCCESS],
                                     finalResult=SUCCESS,
                                     resultText=["succeeded", "succeeded"],
                                     verifiedScore=1)
        return d

    def test_buildsetComplete_failure_sends_summary_review(self):
        d = self.check_summary_build(buildResults=[FAILURE, FAILURE],
                                     finalResult=FAILURE,
                                     resultText=["failed", "failed"],
                                     verifiedScore=-1)
        return d

    def test_buildsetComplete_mixed_sends_summary_review(self):
        d = self.check_summary_build(buildResults=[SUCCESS, FAILURE],
                                     finalResult=FAILURE,
                                     resultText=["succeeded", "failed"],
                                     verifiedScore=-1)
        return d

    def test_buildsetComplete_success_sends_summary_review_legacy(self):
        d = self.check_summary_build_legacy(buildResults=[SUCCESS, SUCCESS],
                                            finalResult=SUCCESS,
                                            resultText=["succeeded", "succeeded"],
                                            verifiedScore=1)
        return d

    def test_buildsetComplete_failure_sends_summary_review_legacy(self):
        d = self.check_summary_build_legacy(buildResults=[FAILURE, FAILURE],
                                            finalResult=FAILURE,
                                            resultText=["failed", "failed"],
                                            verifiedScore=-1)
        return d

    def test_buildsetComplete_mixed_sends_summary_review_legacy(self):
        d = self.check_summary_build_legacy(buildResults=[SUCCESS, FAILURE],
                                            finalResult=FAILURE,
                                            resultText=["succeeded", "failed"],
                                            verifiedScore=-1)
        return d

    @defer.inlineCallbacks
    def test_buildsetComplete_filtered_builder(self):
        gsp = yield self.setupGerritStatusPush(summaryCB=testSummaryCB)
        gsp.builders = ["foo"]
        yield self.run_fake_summary_build(gsp, [FAILURE, FAILURE], FAILURE,
                                          ["failed", "failed"])

        self.assertFalse(gsp.sendCodeReview.called, "sendCodeReview should not be called")

    @defer.inlineCallbacks
    def test_buildsetComplete_filtered_matching_builder(self):
        gsp = yield self.setupGerritStatusPush(summaryCB=testSummaryCB)
        gsp.builders = ["Builder1"]
        yield self.run_fake_summary_build(gsp, [FAILURE, FAILURE], FAILURE,
                                          ["failed", "failed"])

        self.assertTrue(gsp.sendCodeReview.called, "sendCodeReview should be called")

    @defer.inlineCallbacks
    def run_fake_single_build(self, gsp, buildResult, expWarning=False):
        buildset, builds = yield self.setupBuildResults([buildResult], buildResult)

        yield gsp.buildStarted(None, builds[0])
        yield gsp.buildComplete(None, builds[0])

        if expWarning:
            self.assertEqual([w['message'] for w in self.flushWarnings()],
                             ['The Gerrit status callback uses the old '
                              'way to communicate results.  The outcome '
                              'might be not what is expected.'])

        defer.returnValue(str({'name': u'Builder0', 'result': buildResult}))

    # same goes for check_single_build and check_single_build_legacy
    @defer.inlineCallbacks
    def check_single_build(self, buildResult, verifiedScore):

        gsp = yield self.setupGerritStatusPush(reviewCB=testReviewCB,
                                               startCB=testStartCB)

        msg = yield self.run_fake_single_build(gsp, buildResult)
        start = makeReviewResult(str({'name': self.TEST_BUILDER_NAME}),
                                 (GERRIT_LABEL_REVIEWED, 0))
        result = makeReviewResult(msg,
                                  (GERRIT_LABEL_VERIFIED, verifiedScore))
        calls = [call(self.TEST_PROJECT, self.TEST_REVISION, start),
                 call(self.TEST_PROJECT, self.TEST_REVISION, result)]
        gsp.sendCodeReview.assert_has_calls(calls)

    @defer.inlineCallbacks
    def check_single_build_legacy(self, buildResult, verifiedScore):
        gsp = yield self.setupGerritStatusPush(reviewCB=legacyTestReviewCB,
                                               startCB=testStartCB)

        msg = yield self.run_fake_single_build(gsp, buildResult, expWarning=True)

        start = makeReviewResult(str({'name': self.TEST_BUILDER_NAME}),
                                 (GERRIT_LABEL_REVIEWED, 0))
        result = makeReviewResult(msg,
                                  (GERRIT_LABEL_VERIFIED, verifiedScore),
                                  (GERRIT_LABEL_REVIEWED, 0))
        calls = [call(self.TEST_PROJECT, self.TEST_REVISION, start),
                 call(self.TEST_PROJECT, self.TEST_REVISION, result)]
        gsp.sendCodeReview.assert_has_calls(calls)

    def test_buildComplete_success_sends_review(self):
        return self.check_single_build(SUCCESS, 1)

    def test_buildComplete_failure_sends_review(self):
        return self.check_single_build(FAILURE, -1)

    def test_buildComplete_success_sends_review_legacy(self):
        return self.check_single_build_legacy(SUCCESS, 1)

    def test_buildComplete_failure_sends_review_legacy(self):
        return self.check_single_build_legacy(FAILURE, -1)

    # same goes for check_single_build and check_single_build_legacy
    @defer.inlineCallbacks
    def test_single_build_filtered(self):

        gsp = yield self.setupGerritStatusPush(reviewCB=testReviewCB,
                                               startCB=testStartCB)

        gsp.builders = ["Builder0"]
        yield self.run_fake_single_build(gsp, SUCCESS)
        self.assertTrue(gsp.sendCodeReview.called, "sendCodeReview should be called")
        gsp.sendCodeReview = Mock()
        gsp.builders = ["foo"]
        yield self.run_fake_single_build(gsp, SUCCESS)
        self.assertFalse(gsp.sendCodeReview.called, "sendCodeReview should not be called")

    def test_defaultReviewCBSuccess(self):
        res = defaultReviewCB("builderName", {}, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': 1})
        res = defaultReviewCB("builderName", {}, RETRY, None, None)
        self.assertEqual(res['labels'], {})

    def test_defaultSummaryCB(self):
        info = self.makeBuildInfo([SUCCESS, FAILURE], ["yes", "no"])
        res = defaultSummaryCB(info, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': -1})
        info = self.makeBuildInfo([SUCCESS, SUCCESS], ["yes", "yes"])
        res = defaultSummaryCB(info, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': 1})

    @defer.inlineCallbacks
    def testBuildGerritCommand(self):
        gsp = yield self.setupGerritStatusPushSimple()
        spawnSkipFirstArg = Mock()
        gsp.spawnProcess = lambda _, *a, **k: spawnSkipFirstArg(*a, **k)
        yield gsp.sendCodeReview("project", "revision", {"message": "bla", "labels": {'Verified': 1}})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh', ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'version'])
        gsp.processVersion("2.6", lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.sendCodeReview("project", "revision", {"message": "bla", "labels": {'Verified': 1}})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'review',
             '--project project', "--message 'bla'", '--label Verified=1', 'revision'])

        # <=2.5 uses other syntax
        gsp.processVersion("2.4", lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.sendCodeReview("project", "revision", {"message": "bla", "labels": {'Verified': 1}})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'review', '--project project',
             "--message 'bla'", '--verified 1', 'revision'])
