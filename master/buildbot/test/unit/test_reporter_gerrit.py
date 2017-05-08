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

from __future__ import absolute_import
from __future__ import print_function
from future.builtins import range

import warnings
from distutils.version import LooseVersion

from mock import Mock
from mock import call

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.reporters import utils
from buildbot.reporters.gerrit import GERRIT_LABEL_REVIEWED
from buildbot.reporters.gerrit import GERRIT_LABEL_VERIFIED
from buildbot.reporters.gerrit import GerritStatusPush
from buildbot.reporters.gerrit import defaultReviewCB
from buildbot.reporters.gerrit import defaultSummaryCB
from buildbot.reporters.gerrit import makeReviewResult
from buildbot.test.fake import fakemaster
from buildbot.test.util.reporter import ReporterTestMixin

warnings.filterwarnings('error', message='.*Gerrit status')


def sampleReviewCB(builderName, build, result, status, arg):
    verified = 1 if result == SUCCESS else -1
    return makeReviewResult(str({'name': builderName, 'result': result}),
                            (GERRIT_LABEL_VERIFIED, verified))


@defer.inlineCallbacks
def sampleReviewCBDeferred(builderName, build, result, status, arg):
    verified = 1 if result == SUCCESS else -1
    result = yield makeReviewResult(str({'name': builderName, 'result': result}),
                                    (GERRIT_LABEL_VERIFIED, verified))
    defer.returnValue(result)


def sampleStartCB(builderName, build, arg):
    return makeReviewResult(str({'name': builderName}),
                            (GERRIT_LABEL_REVIEWED, 0))


@defer.inlineCallbacks
def sampleStartCBDeferred(builderName, build, arg):
    result = yield makeReviewResult(str({'name': builderName}),
                                    (GERRIT_LABEL_REVIEWED, 0))
    defer.returnValue(result)


def sampleSummaryCB(buildInfoList, results, status, arg):
    success = False
    failure = False

    for buildInfo in buildInfoList:
        if buildInfo['result'] == SUCCESS:  # pylint: disable=simplifiable-if-statement
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


@defer.inlineCallbacks
def sampleSummaryCBDeferred(buildInfoList, results, master, arg):
    success = False
    failure = False

    for buildInfo in buildInfoList:
        if buildInfo['result'] == SUCCESS:  # pylint: disable=simplifiable-if-statement
            success = True
        else:
            failure = True

    if failure:
        verified = -1
    elif success:
        verified = 1
    else:
        verified = 0

    result = yield makeReviewResult(str(buildInfoList),
                                    (GERRIT_LABEL_VERIFIED, verified))
    defer.returnValue(result)


def legacyTestReviewCB(builderName, build, result, status, arg):
    msg = str({'name': builderName, 'result': result})
    return (msg, 1 if result == SUCCESS else -1, 0)


def legacyTestSummaryCB(buildInfoList, results, status, arg):
    success = False
    failure = False

    for buildInfo in buildInfoList:
        if buildInfo['result'] == SUCCESS:  # pylint: disable=simplifiable-if-statement
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


class TestGerritStatusPush(unittest.TestCase, ReporterTestMixin):

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
        self.insertTestData(buildResults, finalResult)
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

    def makeBuildInfo(self, buildResults, resultText, builds):
        info = []
        for i in range(len(buildResults)):
            info.append({'name': u"Builder%d" % i, 'result': buildResults[i],
                         'resultText': resultText[i], 'text': u'buildText',
                         'url': "http://localhost:8080/#builders/%d/builds/%d" % (79 + i, i),
                         'build': builds[i]})
        return info

    @defer.inlineCallbacks
    def run_fake_summary_build(self, gsp, buildResults, finalResult,
                               resultText, expWarning=False):
        buildset, builds = yield self.setupBuildResults(buildResults, finalResult)
        yield gsp.buildsetComplete('buildset.98.complete'.split("."),
                                   buildset)

        info = self.makeBuildInfo(buildResults, resultText, builds)
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
    def check_summary_build_deferred(self, buildResults, finalResult, resultText,
                                     verifiedScore):
        gsp = yield self.setupGerritStatusPush(summaryCB=sampleSummaryCBDeferred)

        msg = yield self.run_fake_summary_build(gsp, buildResults, finalResult,
                                                resultText)

        result = makeReviewResult(msg,
                                  (GERRIT_LABEL_VERIFIED, verifiedScore))
        gsp.sendCodeReview.assert_called_once_with(self.TEST_PROJECT,
                                                   self.TEST_REVISION,
                                                   result)

    @defer.inlineCallbacks
    def check_summary_build(self, buildResults, finalResult, resultText,
                            verifiedScore):
        gsp = yield self.setupGerritStatusPush(summaryCB=sampleSummaryCB)

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

        expected1 = [
            'ssh', 'buildbot@example.com', '-p', '29418', 'gerrit', 'foo']
        self.assertEqual(expected1, without_identity._gerritCmd('foo'))
        yield without_identity.disownServiceParent()
        with_identity = yield self.setupGerritStatusPush(
            identity_file='/path/to/id_rsa', **kwargs)
        expected2 = [
            'ssh', '-i', '/path/to/id_rsa', 'buildbot@example.com', '-p', '29418',
            'gerrit', 'foo',
        ]
        self.assertEqual(expected2, with_identity._gerritCmd('foo'))

    def test_buildsetComplete_success_sends_summary_review_deferred(self):
        d = self.check_summary_build_deferred(buildResults=[SUCCESS, SUCCESS],
                                              finalResult=SUCCESS,
                                              resultText=[
                                                  "succeeded", "succeeded"],
                                              verifiedScore=1)
        return d

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
                                            resultText=[
                                                "succeeded", "succeeded"],
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
        gsp = yield self.setupGerritStatusPush(summaryCB=sampleSummaryCB)
        gsp.builders = ["foo"]
        yield self.run_fake_summary_build(gsp, [FAILURE, FAILURE], FAILURE,
                                          ["failed", "failed"])

        self.assertFalse(
            gsp.sendCodeReview.called, "sendCodeReview should not be called")

    @defer.inlineCallbacks
    def test_buildsetComplete_filtered_matching_builder(self):
        gsp = yield self.setupGerritStatusPush(summaryCB=sampleSummaryCB)
        gsp.builders = ["Builder1"]
        yield self.run_fake_summary_build(gsp, [FAILURE, FAILURE], FAILURE,
                                          ["failed", "failed"])

        self.assertTrue(
            gsp.sendCodeReview.called, "sendCodeReview should be called")

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

        gsp = yield self.setupGerritStatusPush(reviewCB=sampleReviewCB,
                                               startCB=sampleStartCB)

        msg = yield self.run_fake_single_build(gsp, buildResult)
        start = makeReviewResult(str({'name': self.TEST_BUILDER_NAME}),
                                 (GERRIT_LABEL_REVIEWED, 0))
        result = makeReviewResult(msg,
                                  (GERRIT_LABEL_VERIFIED, verifiedScore))
        calls = [call(self.TEST_PROJECT, self.TEST_REVISION, start),
                 call(self.TEST_PROJECT, self.TEST_REVISION, result)]
        gsp.sendCodeReview.assert_has_calls(calls)

    # same goes for check_single_build and check_single_build_legacy
    @defer.inlineCallbacks
    def check_single_build_deferred(self, buildResult, verifiedScore):

        gsp = yield self.setupGerritStatusPush(reviewCB=sampleReviewCBDeferred,
                                               startCB=sampleStartCBDeferred)

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
                                               startCB=sampleStartCB)

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

        gsp = yield self.setupGerritStatusPush(reviewCB=sampleReviewCB,
                                               startCB=sampleStartCB)

        gsp.builders = ["Builder0"]
        yield self.run_fake_single_build(gsp, SUCCESS)
        self.assertTrue(
            gsp.sendCodeReview.called, "sendCodeReview should be called")
        gsp.sendCodeReview = Mock()
        gsp.builders = ["foo"]
        yield self.run_fake_single_build(gsp, SUCCESS)
        self.assertFalse(
            gsp.sendCodeReview.called, "sendCodeReview should not be called")

    def test_defaultReviewCBSuccess(self):
        res = defaultReviewCB("builderName", {}, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': 1})
        res = defaultReviewCB("builderName", {}, RETRY, None, None)
        self.assertEqual(res['labels'], {})

    def test_defaultSummaryCB(self):
        info = self.makeBuildInfo(
            [SUCCESS, FAILURE], ["yes", "no"], [None, None])
        res = defaultSummaryCB(info, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': -1})
        info = self.makeBuildInfo(
            [SUCCESS, SUCCESS], ["yes", "yes"], [None, None])
        res = defaultSummaryCB(info, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': 1})

    @defer.inlineCallbacks
    def testBuildGerritCommand(self):
        gsp = yield self.setupGerritStatusPushSimple()
        spawnSkipFirstArg = Mock()
        gsp.spawnProcess = lambda _, *a, **k: spawnSkipFirstArg(*a, **k)
        yield gsp.sendCodeReview("project", "revision", {"message": "bla", "labels": {'Verified': 1}})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh', ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'version'], env=None)
        gsp.processVersion("2.6", lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.sendCodeReview("project", "revision", {"message": "bla", "labels": {'Verified': 1}})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'review',
             '--project project', "--message 'bla'", '--label Verified=1', 'revision'], env=None)

        # <=2.5 uses other syntax
        gsp.processVersion("2.4", lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.sendCodeReview("project", "revision", {"message": "bla", "labels": {'Verified': 1}})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'review', '--project project',
             "--message 'bla'", '--verified 1', 'revision'], env=None)

        # now test the notify argument, even though _gerrit_notify
        # is private, work around that
        gsp._gerrit_notify = 'OWNER'
        gsp.processVersion('2.6', lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.sendCodeReview('project', 'revision', {'message': 'bla', 'labels': {'Verified': 1}})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'review',
             '--project project', '--notify OWNER', "--message 'bla'", '--label Verified=1', 'revision'],
            env=None)

        # gerrit versions <= 2.5 uses other syntax
        gsp.processVersion('2.4', lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.sendCodeReview('project', 'revision', {'message': 'bla', 'labels': {'Verified': 1}})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'review', '--project project', '--notify OWNER',
             "--message 'bla'", '--verified 1', 'revision'],
            env=None)

    @defer.inlineCallbacks
    def test_callWithVersion_bytes_output(self):
        gsp = yield self.setupGerritStatusPushSimple()
        exp_argv = ['ssh', 'user@serv', '-p', '29418', 'gerrit', 'version']

        def spawnProcess(pp, cmd, argv, env):
            self.assertEqual([cmd, argv], [exp_argv[0], exp_argv])
            pp.errReceived(b'test stderr\n')
            pp.outReceived(b'gerrit version 2.14\n')
            pp.outReceived(b'(garbage that should not cause a crash)\n')
            so = error.ProcessDone(None)
            pp.processEnded(failure.Failure(so))
        self.patch(reactor, 'spawnProcess', spawnProcess)
        gsp.callWithVersion(lambda: self.assertEqual(
            gsp.gerrit_version, LooseVersion('2.14')))
