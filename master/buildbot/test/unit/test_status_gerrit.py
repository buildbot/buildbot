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
from buildbot.status.status_gerrit import GerritStatusPush
from buildbot.status.status_gerrit import makeReviewResult
from buildbot.status.status_gerrit import GERRIT_LABEL_VERIFIED
from buildbot.status.status_gerrit import GERRIT_LABEL_REVIEWED
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuildStatus
from mock import Mock
from twisted.trial import unittest
from twisted.internet import defer


def testReviewCB(builderName, build, result, status, arg):
    verified = 1 if result == SUCCESS else -1
    return makeReviewResult(str({'name': builderName, 'result': result}),
                            (GERRIT_LABEL_VERIFIED, verified))


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
    TEST_PROPS = {
        'gerrit_branch': 'refs/changes/34/1234/1',
        'project': TEST_PROJECT,
        'got_revision': TEST_REVISION,
    }
    THING_URL = 'http://thing.example.com'

    def run_fake_summary_build(self, gsp, buildResults, finalResult, resultText):
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

        gsp.master.db = fakedb.FakeDBConnector(gsp.master, self)

        fakedata = [
            fakedb.Master(id=92),
            fakedb.Buildslave(id=13, name='sl'),
            fakedb.Buildset(id=99, results=finalResult, reason="testReason"),
        ]

        breqid = 1000
        for (builder, build) in buildpairs:
            fakedata.append(fakedb.BuildRequest(id=breqid, buildsetid=99,
                                                buildername=builder.name))
            fakedata.append(fakedb.Build(number=0, buildrequestid=breqid,
                                         masterid=92, buildslaveid=13))
            breqid = breqid + 1

        gsp.master.db.insertTestData(fakedata)

        d = gsp._buildsetComplete('buildset.99.complete',
                                  dict(bsid=99, result=SUCCESS))

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

        gsp.buildFinished('dummyBuilder', build, buildResult)

        return defer.succeed(str({'name': 'dummyBuilder', 'result': buildResult}))

    # same goes for check_single_build and check_single_build_legacy

    def check_single_build(self, buildResult, verifiedScore):
        gsp = _get_prepared_gsp(reviewCB=testReviewCB)

        d = self.run_fake_single_build(gsp, buildResult)

        @d.addCallback
        def check(msg):
            result = makeReviewResult(msg,
                                      (GERRIT_LABEL_VERIFIED, verifiedScore))
            gsp.sendCodeReview.assert_called_once_with(self.TEST_PROJECT,
                                                       self.TEST_REVISION,
                                                       result)
        return d

    def check_single_build_legacy(self, buildResult, verifiedScore):
        gsp = _get_prepared_gsp(reviewCB=legacyTestReviewCB)

        d = self.run_fake_single_build(gsp, buildResult)

        @d.addCallback
        def check(msg):
            result = makeReviewResult(msg,
                                      (GERRIT_LABEL_VERIFIED, verifiedScore),
                                      (GERRIT_LABEL_REVIEWED, 0))
            gsp.sendCodeReview.assert_called_once_with(self.TEST_PROJECT,
                                                       self.TEST_REVISION,
                                                       result)
        return d

    def test_buildsetComplete_success_sends_review(self):
        self.check_single_build(SUCCESS, 1)

    def test_buildsetComplete_failure_sends_review(self):
        self.check_single_build(FAILURE, -1)

    def test_buildsetComplete_success_sends_review_legacy(self):
        self.check_single_build_legacy(SUCCESS, 1)

    def test_buildsetComplete_failure_sends_review_legacy(self):
        self.check_single_build_legacy(FAILURE, -1)
