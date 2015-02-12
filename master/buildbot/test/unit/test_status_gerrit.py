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

from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.status.status_gerrit import GERRIT_LABEL_REVIEWED
from buildbot.status.status_gerrit import GERRIT_LABEL_VERIFIED
from buildbot.status.status_gerrit import GerritStatusPush
from buildbot.status.status_gerrit import makeReviewResult
from buildbot.test.fake.fakebuild import FakeBuildStatus
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from mock import call, Mock
from twisted.internet import defer
from twisted.trial import unittest


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


def _get_prepared_gsp(*args, **kwargs):
    """
    get an instance of GerritStatusPush prepared for testing

    Hostname and username are "hardcoded", the rest is taken from the provided
    parameters.
    """
    gsp = GerritStatusPush('host.example.com', 'username', *args, **kwargs)

    gsp.master = fakemaster.make_master()
    gsp.master_status = gsp.master.status

    gsp.sendCodeReview = Mock()

    return gsp


class TestGerritStatusPush(unittest.TestCase):

    TEST_PROJECT = 'testProject'
    TEST_REVISION = 'd34db33fd43db33f'
    TEST_CHANGE_ID = 'I5bdc2e500d00607af53f0fa4df661aada17f81fc'
    TEST_BUILDER_NAME = 'dummyBuilder'
    TEST_PROPS = {
        'gerrit_branch': 'refs/changes/34/1234/1',
        'project': TEST_PROJECT,
        'got_revision': TEST_REVISION,
        'revision': TEST_REVISION,
        'event.change.id': TEST_CHANGE_ID
    }
    THING_URL = 'http://thing.example.com'

    def run_fake_summary_build(self, gsp, buildResults, finalResult,
                               resultText):
        buildpairs = []
        i = 0
        for i in xrange(len(buildResults)):
            buildResult = buildResults[i]

            builder = Mock()
            build = FakeBuildStatus()

            builder.getBuild.return_value = build
            builder.name = "Builder-%d" % i
            builder.getName.return_value = builder.name

            build.results = buildResult
            build.finished = True
            build.reason = "testReason"
            build.getBuilder.return_value = builder
            build.getResults.return_value = build.results
            build.getText.return_value = ['buildText']
            build.getProperty = self.TEST_PROPS.get

            buildpairs.append((builder, build))

        def fakeGetBuilder(buildername):
            # e.g. Builder-5 will be buildpairs[5][0]
            return buildpairs[int(buildername.split("-")[1])][0]

        gsp.master_status.getBuilder = fakeGetBuilder
        gsp.master_status.getURLForThing = Mock()
        gsp.master_status.getURLForThing.return_value = self.THING_URL

        gsp.master.db = fakedb.FakeDBConnector(self)

        fakedata = [
            fakedb.SourceStampSet(id=127),
            fakedb.Buildset(id=99, sourcestampsetid=127, results=finalResult, reason="testReason")
        ]

        breqid = 1000
        for (builder, build) in buildpairs:
            fakedata.append(fakedb.BuildRequest(id=breqid, buildsetid=99,
                                                buildername=builder.name))
            fakedata.append(fakedb.Build(number=0, brid=breqid))
            breqid = breqid + 1

        gsp.master.db.insertTestData(fakedata)

        d = gsp._buildsetComplete(99, finalResult)

        @d.addCallback
        def check(_):
            info = []
            for i in xrange(len(buildResults)):
                info.append({'name': "Builder-%d" % i, 'result': buildResults[i],
                             'resultText': resultText[i], 'text': 'buildText',
                             'url': self.THING_URL})
            return str(info)
        return d

    # check_summary_build and check_summary_build_legacy differ in two things:
    #   * the callback used
    #   * the expected result

    def check_summary_build(self, buildResults, finalResult, resultText,
                            verifiedScore):
        gsp = _get_prepared_gsp(summaryCB=testSummaryCB)

        d = self.run_fake_summary_build(gsp, buildResults, finalResult,
                                        resultText)

        @d.addCallback
        def check(msg):
            result = makeReviewResult(msg,
                                      (GERRIT_LABEL_VERIFIED, verifiedScore))
            gsp.sendCodeReview.assert_called_once_with(self.TEST_PROJECT,
                                                       self.TEST_REVISION,
                                                       result)
        return d

    def check_summary_build_legacy(self, buildResults, finalResult, resultText,
                                   verifiedScore):
        gsp = _get_prepared_gsp(summaryCB=legacyTestSummaryCB)

        d = self.run_fake_summary_build(gsp, buildResults, finalResult,
                                        resultText)

        @d.addCallback
        def check(msg):
            result = makeReviewResult(msg,
                                      (GERRIT_LABEL_VERIFIED, verifiedScore),
                                      (GERRIT_LABEL_REVIEWED, 0))
            gsp.sendCodeReview.assert_called_once_with(self.TEST_PROJECT,
                                                       self.TEST_REVISION,
                                                       result)
        return d

    def test_gerrit_ssh_cmd(self):
        kwargs = {
            'server': 'example.com',
            'username': 'buildbot',
        }
        without_identity = GerritStatusPush(**kwargs)

        expected1 = ['ssh', 'buildbot@example.com', '-p', '29418', 'gerrit', 'foo']
        self.assertEqual(expected1, without_identity._gerritCmd('foo'))

        with_identity = GerritStatusPush(
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

    def run_fake_single_build(self, gsp, buildResult):
        build = FakeBuildStatus(name="build")
        build.getProperty = self.TEST_PROPS.get

        gsp.buildStarted(self.TEST_BUILDER_NAME, build)
        gsp.buildFinished(self.TEST_BUILDER_NAME, build, buildResult)

        return defer.succeed(str({'name': self.TEST_BUILDER_NAME,
                                  'result': buildResult}))

    # same goes for check_single_build and check_single_build_legacy

    def check_single_build(self, buildResult, verifiedScore):
        gsp = _get_prepared_gsp(reviewCB=testReviewCB, startCB=testStartCB)

        d = self.run_fake_single_build(gsp, buildResult)

        @d.addCallback
        def check(msg):
            start = makeReviewResult(str({'name': self.TEST_BUILDER_NAME}),
                                     (GERRIT_LABEL_REVIEWED, 0))
            result = makeReviewResult(msg,
                                      (GERRIT_LABEL_VERIFIED, verifiedScore))
            calls = [call(self.TEST_PROJECT, self.TEST_REVISION, start),
                     call(self.TEST_PROJECT, self.TEST_REVISION, result)]
            gsp.sendCodeReview.assert_has_calls(calls)

        return d

    def check_single_build_legacy(self, buildResult, verifiedScore):
        gsp = _get_prepared_gsp(reviewCB=legacyTestReviewCB,
                                startCB=testStartCB)

        d = self.run_fake_single_build(gsp, buildResult)

        @d.addCallback
        def check(msg):
            start = makeReviewResult(str({'name': self.TEST_BUILDER_NAME}),
                                     (GERRIT_LABEL_REVIEWED, 0))
            result = makeReviewResult(msg,
                                      (GERRIT_LABEL_VERIFIED, verifiedScore),
                                      (GERRIT_LABEL_REVIEWED, 0))
            calls = [call(self.TEST_PROJECT, self.TEST_REVISION, start),
                     call(self.TEST_PROJECT, self.TEST_REVISION, result)]
            gsp.sendCodeReview.assert_has_calls(calls)

        return d

    def test_buildsetComplete_success_sends_review(self):
        self.check_single_build(SUCCESS, 1)

    def test_buildsetComplete_failure_sends_review(self):
        self.check_single_build(FAILURE, -1)

    def test_buildsetComplete_success_sends_review_legacy(self):
        self.check_single_build_legacy(SUCCESS, 1)

    def test_buildsetComplete_failure_sends_review_legacy(self):
        self.check_single_build_legacy(FAILURE, -1)
