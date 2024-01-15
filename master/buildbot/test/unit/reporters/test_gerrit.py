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

import warnings
from unittest.mock import Mock
from unittest.mock import call

from packaging.version import parse as parse_version
from parameterized import parameterized
from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.reporters import utils
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.generators.buildset import BuildSetStatusGenerator
from buildbot.reporters.gerrit import GERRIT_LABEL_REVIEWED
from buildbot.reporters.gerrit import GERRIT_LABEL_VERIFIED
from buildbot.reporters.gerrit import GerritStatusPush
from buildbot.reporters.gerrit import defaultReviewCB
from buildbot.reporters.gerrit import defaultSummaryCB
from buildbot.reporters.gerrit import extract_project_revision
from buildbot.reporters.gerrit import makeReviewResult
from buildbot.reporters.message import MessageFormatterFunctionRaw
from buildbot.reporters.message import MessageFormatterRenderable
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning

warnings.filterwarnings('error', message='.*Gerrit status')


def sampleReviewCB(builderName, build, result, status, arg):
    verified = 1 if result == SUCCESS else -1
    return makeReviewResult(
        str({'name': builderName, 'result': result}), (GERRIT_LABEL_VERIFIED, verified)
    )


@defer.inlineCallbacks
def sampleReviewCBDeferred(builderName, build, result, status, arg):
    verified = 1 if result == SUCCESS else -1
    result = yield makeReviewResult(
        str({'name': builderName, 'result': result}), (GERRIT_LABEL_VERIFIED, verified)
    )
    return result


def sampleStartCB(builderName, build, arg):
    return makeReviewResult(str({'name': builderName}), (GERRIT_LABEL_REVIEWED, 0))


@defer.inlineCallbacks
def sampleStartCBDeferred(builderName, build, arg):
    result = yield makeReviewResult(str({'name': builderName}), (GERRIT_LABEL_REVIEWED, 0))
    return result


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

    return makeReviewResult(str(buildInfoList), (GERRIT_LABEL_VERIFIED, verified))


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

    result = yield makeReviewResult(str(buildInfoList), (GERRIT_LABEL_VERIFIED, verified))
    return result


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


class TestGerritStatusPush(TestReactorMixin, unittest.TestCase, ReporterTestMixin):
    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def setupGerritStatusPushSimple(self, *args, **kwargs):
        serv = kwargs.pop("server", "serv")
        username = kwargs.pop("username", "user")
        gsp = GerritStatusPush(serv, username, *args, **kwargs)
        yield gsp.setServiceParent(self.master)
        yield gsp.startService()
        return gsp

    @defer.inlineCallbacks
    def setupGerritStatusPush(self, *args, **kwargs):
        gsp = yield self.setupGerritStatusPushSimple(*args, **kwargs)
        gsp.send_code_review = Mock()
        return gsp

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults, finalResult):
        self.insert_test_data(buildResults, finalResult)
        res = yield utils.getDetailsForBuildset(self.master, 98, want_properties=True)
        builds = res['builds']
        buildset = res['buildset']

        @defer.inlineCallbacks
        def getChangesForBuild(buildid):
            assert buildid == 20
            ch = yield self.master.db.changes.getChange(13)
            return [ch]

        self.master.db.changes.getChangesForBuild = getChangesForBuild
        return (buildset, builds)

    def makeBuildInfo(self, buildResults, resultText, builds):
        info = []
        for i, buildResult in enumerate(buildResults):
            info.append({
                'name': f"Builder{i}",
                'result': buildResult,
                'resultText': resultText[i],
                'text': 'buildText',
                'url': f"http://localhost:8080/#/builders/{79 + i}/builds/{i}",
                'build': builds[i],
            })
        return info

    @defer.inlineCallbacks
    def run_fake_summary_build(self, gsp, buildResults, finalResult, resultText, expWarning=False):
        buildset, builds = yield self.setupBuildResults(buildResults, finalResult)
        yield gsp._got_event(("buildsets", 98, "complete"), buildset)

        info = self.makeBuildInfo(buildResults, resultText, builds)
        if expWarning:
            self.assertEqual(
                [w['message'] for w in self.flushWarnings()],
                [
                    'The Gerrit status callback uses the old '
                    'way to communicate results.  The outcome '
                    'might be not what is expected.'
                ],
            )
        return str(info)

    # check_summary_build and check_summary_build_legacy differ in two things:
    #   * the callback used
    #   * the expected result

    @defer.inlineCallbacks
    def check_summary_build_deferred(self, buildResults, finalResult, resultText, verifiedScore):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern="Use generators instead"):
            gsp = yield self.setupGerritStatusPush(summaryCB=sampleSummaryCBDeferred)

        msg = yield self.run_fake_summary_build(gsp, buildResults, finalResult, resultText)

        gsp.send_code_review.assert_called_once_with(
            self.reporter_test_project,
            self.reporter_test_revision,
            msg,
            {GERRIT_LABEL_VERIFIED: verifiedScore},
        )

    @defer.inlineCallbacks
    def check_summary_build(self, buildResults, finalResult, resultText, verifiedScore):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern="Use generators instead"):
            gsp = yield self.setupGerritStatusPush(summaryCB=sampleSummaryCB)

        msg = yield self.run_fake_summary_build(gsp, buildResults, finalResult, resultText)

        gsp.send_code_review.assert_called_once_with(
            self.reporter_test_project,
            self.reporter_test_revision,
            msg,
            {GERRIT_LABEL_VERIFIED: verifiedScore},
        )

    @defer.inlineCallbacks
    def check_summary_build_legacy(self, buildResults, finalResult, resultText, verifiedScore):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern="Use generators instead"):
            gsp = yield self.setupGerritStatusPush(summaryCB=legacyTestSummaryCB)

        msg = yield self.run_fake_summary_build(
            gsp, buildResults, finalResult, resultText, expWarning=True
        )

        gsp.send_code_review.assert_called_once_with(
            self.reporter_test_project,
            self.reporter_test_revision,
            msg,
            {GERRIT_LABEL_VERIFIED: verifiedScore, GERRIT_LABEL_REVIEWED: 0},
        )

    @defer.inlineCallbacks
    def test_gerrit_ssh_cmd(self):
        kwargs = {
            'server': 'example.com',
            'username': 'buildbot',
        }
        without_identity = yield self.setupGerritStatusPush(**kwargs)

        expected1 = [
            'ssh',
            '-o',
            'BatchMode=yes',
            'buildbot@example.com',
            '-p',
            '29418',
            'gerrit',
            'foo',
        ]
        self.assertEqual(expected1, without_identity._gerritCmd('foo'))
        yield without_identity.disownServiceParent()
        with_identity = yield self.setupGerritStatusPush(identity_file='/path/to/id_rsa', **kwargs)
        expected2 = [
            'ssh',
            '-o',
            'BatchMode=yes',
            '-i',
            '/path/to/id_rsa',
            'buildbot@example.com',
            '-p',
            '29418',
            'gerrit',
            'foo',
        ]
        self.assertEqual(expected2, with_identity._gerritCmd('foo'))

    def test_buildsetComplete_success_sends_summary_review_deferred(self):
        d = self.check_summary_build_deferred(
            buildResults=[SUCCESS, SUCCESS],
            finalResult=SUCCESS,
            resultText=["succeeded", "succeeded"],
            verifiedScore=1,
        )
        return d

    def test_buildsetComplete_success_sends_summary_review(self):
        d = self.check_summary_build(
            buildResults=[SUCCESS, SUCCESS],
            finalResult=SUCCESS,
            resultText=["succeeded", "succeeded"],
            verifiedScore=1,
        )
        return d

    def test_buildsetComplete_failure_sends_summary_review(self):
        d = self.check_summary_build(
            buildResults=[FAILURE, FAILURE],
            finalResult=FAILURE,
            resultText=["failed", "failed"],
            verifiedScore=-1,
        )
        return d

    def test_buildsetComplete_mixed_sends_summary_review(self):
        d = self.check_summary_build(
            buildResults=[SUCCESS, FAILURE],
            finalResult=FAILURE,
            resultText=["succeeded", "failed"],
            verifiedScore=-1,
        )
        return d

    def test_buildsetComplete_success_sends_summary_review_legacy(self):
        d = self.check_summary_build_legacy(
            buildResults=[SUCCESS, SUCCESS],
            finalResult=SUCCESS,
            resultText=["succeeded", "succeeded"],
            verifiedScore=1,
        )
        return d

    def test_buildsetComplete_failure_sends_summary_review_legacy(self):
        d = self.check_summary_build_legacy(
            buildResults=[FAILURE, FAILURE],
            finalResult=FAILURE,
            resultText=["failed", "failed"],
            verifiedScore=-1,
        )
        return d

    def test_buildsetComplete_mixed_sends_summary_review_legacy(self):
        d = self.check_summary_build_legacy(
            buildResults=[SUCCESS, FAILURE],
            finalResult=FAILURE,
            resultText=["succeeded", "failed"],
            verifiedScore=-1,
        )
        return d

    @parameterized.expand([
        ("matched", ["Builder1"], True),
        ("not_matched", ["foo"], False),
    ])
    @defer.inlineCallbacks
    def test_buildset_complete_filtered_builder(self, name, builders, should_call):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern="Use generators instead"):
            gsp = yield self.setupGerritStatusPush(summaryCB=sampleSummaryCB, builders=builders)

        yield self.run_fake_summary_build(gsp, [FAILURE, FAILURE], FAILURE, ["failed", "failed"])

        self.assertEqual(gsp.send_code_review.called, should_call)

    @defer.inlineCallbacks
    def run_fake_single_build(self, gsp, buildResult, expWarning=False):
        _, builds = yield self.setupBuildResults([None], None)

        yield gsp._got_event(('builds', builds[0]['buildid'], 'new'), builds[0])

        yield self.master.db.builds.finishBuild(builds[0]["buildid"], buildResult)
        yield self.master.db.buildsets.completeBuildset(98, buildResult)

        res = yield utils.getDetailsForBuildset(self.master, 98, want_properties=True)
        builds = res['builds']

        yield gsp._got_event(('builds', builds[0]['buildid'], 'finished'), builds[0])

        if expWarning:
            self.assertEqual(
                [w['message'] for w in self.flushWarnings()],
                [
                    'The Gerrit status callback uses the old '
                    'way to communicate results.  The outcome '
                    'might be not what is expected.'
                ],
            )

        return str({'name': 'Builder0', 'result': buildResult})

    # same goes for check_single_build and check_single_build_legacy
    @defer.inlineCallbacks
    def check_single_build(self, buildResult, verifiedScore):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern="Use generators instead"):
            gsp = yield self.setupGerritStatusPush(reviewCB=sampleReviewCB, startCB=sampleStartCB)

        msg = yield self.run_fake_single_build(gsp, buildResult)
        calls = [
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                str({'name': self.reporter_test_builder_name}),
                {GERRIT_LABEL_REVIEWED: 0},
            ),
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                msg,
                {GERRIT_LABEL_VERIFIED: verifiedScore},
            ),
        ]
        gsp.send_code_review.assert_has_calls(calls)

    # same goes for check_single_build and check_single_build_legacy
    @defer.inlineCallbacks
    def check_single_build_deferred(self, buildResult, verifiedScore):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern="Use generators instead"):
            gsp = yield self.setupGerritStatusPush(
                reviewCB=sampleReviewCBDeferred, startCB=sampleStartCBDeferred
            )

        msg = yield self.run_fake_single_build(gsp, buildResult)
        calls = [
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                str({'name': self.reporter_test_builder_name}),
                {GERRIT_LABEL_REVIEWED: 0},
            ),
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                msg,
                {GERRIT_LABEL_VERIFIED: verifiedScore},
            ),
        ]
        gsp.send_code_review.assert_has_calls(calls)

    @defer.inlineCallbacks
    def check_single_build_legacy(self, buildResult, verifiedScore):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern="Use generators instead"):
            gsp = yield self.setupGerritStatusPush(
                reviewCB=legacyTestReviewCB, startCB=sampleStartCB
            )

        msg = yield self.run_fake_single_build(gsp, buildResult, expWarning=True)
        calls = [
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                str({'name': self.reporter_test_builder_name}),
                {GERRIT_LABEL_REVIEWED: 0},
            ),
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                msg,
                {GERRIT_LABEL_VERIFIED: verifiedScore, GERRIT_LABEL_REVIEWED: 0},
            ),
        ]
        gsp.send_code_review.assert_has_calls(calls)

    def test_buildComplete_success_sends_review(self):
        return self.check_single_build(SUCCESS, 1)

    def test_buildComplete_failure_sends_review(self):
        return self.check_single_build(FAILURE, -1)

    def test_buildComplete_success_sends_review_legacy(self):
        return self.check_single_build_legacy(SUCCESS, 1)

    def test_buildComplete_failure_sends_review_legacy(self):
        return self.check_single_build_legacy(FAILURE, -1)

    # same goes for check_single_build and check_single_build_legacy
    @parameterized.expand([
        ("matched", ["Builder0"], True),
        ("not_matched", ["foo"], False),
    ])
    @defer.inlineCallbacks
    def test_single_build_filtered(self, name, builders, should_call):
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern="Use generators instead"):
            gsp = yield self.setupGerritStatusPush(
                reviewCB=sampleReviewCB, startCB=sampleStartCB, builders=builders
            )

        yield self.run_fake_single_build(gsp, SUCCESS)
        self.assertEqual(gsp.send_code_review.called, should_call)

    @parameterized.expand([
        ("success", SUCCESS, 1),
        ("failure", FAILURE, -1),
    ])
    @defer.inlineCallbacks
    def test_single_build_generators(self, name, build_result, verified_score):
        gsp = yield self.setupGerritStatusPush(generators=[BuildStartEndStatusGenerator()])

        yield self.run_fake_single_build(gsp, build_result)
        calls = [
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                "Build started.",
                {GERRIT_LABEL_VERIFIED: 0},
            ),
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                "Build done.",
                {GERRIT_LABEL_VERIFIED: verified_score},
            ),
        ]
        gsp.send_code_review.assert_has_calls(calls)

    @parameterized.expand([
        ("success", SUCCESS, 1),
        ("failure", FAILURE, -1),
    ])
    @defer.inlineCallbacks
    def test_single_buildset_generators(self, name, build_result, verified_score):
        gsp = yield self.setupGerritStatusPush(
            generators=[
                BuildSetStatusGenerator(message_formatter=MessageFormatterRenderable("Build done."))
            ]
        )

        yield self.run_fake_summary_build(gsp, [build_result], build_result, "text")
        calls = [
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                "Build done.",
                {GERRIT_LABEL_VERIFIED: verified_score},
            )
        ]
        gsp.send_code_review.assert_has_calls(calls)

    @defer.inlineCallbacks
    def test_single_buildset_generators_override_label(self):
        formatter = MessageFormatterFunctionRaw(
            lambda _, __: {
                "body": "text1",
                "type": "plain",
                "subject": "sub1",
                "extra_info": {"labels": {"Verified": -2}},
            }
        )

        gsp = yield self.setupGerritStatusPush(
            generators=[BuildSetStatusGenerator(message_formatter=formatter)]
        )

        yield self.run_fake_summary_build(gsp, [SUCCESS], SUCCESS, "text")
        calls = [
            call(
                self.reporter_test_project,
                self.reporter_test_revision,
                "text1",
                {GERRIT_LABEL_VERIFIED: -2},
            )
        ]
        gsp.send_code_review.assert_has_calls(calls)

    def test_defaultReviewCBSuccess(self):
        res = defaultReviewCB("builderName", {}, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': 1})
        res = defaultReviewCB("builderName", {}, RETRY, None, None)
        self.assertEqual(res['labels'], {})

    def test_defaultSummaryCB(self):
        info = self.makeBuildInfo([SUCCESS, FAILURE], ["yes", "no"], [None, None])
        res = defaultSummaryCB(info, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': -1})
        info = self.makeBuildInfo([SUCCESS, SUCCESS], ["yes", "yes"], [None, None])
        res = defaultSummaryCB(info, SUCCESS, None, None)
        self.assertEqual(res['labels'], {'Verified': 1})

    @defer.inlineCallbacks
    def testBuildGerritCommand(self):
        gsp = yield self.setupGerritStatusPushSimple()
        spawnSkipFirstArg = Mock()
        gsp.spawnProcess = lambda _, *a, **k: spawnSkipFirstArg(*a, **k)
        yield gsp.send_code_review("project", "revision", "bla", {'Verified': 1})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            ['ssh', '-o', 'BatchMode=yes', 'user@serv', '-p', '29418', 'gerrit', 'version'],
            env=None,
        )
        gsp.processVersion(parse_version("2.6"), lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.send_code_review("project", "revision", "bla", {'Verified': 1})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            [
                'ssh',
                '-o',
                'BatchMode=yes',
                'user@serv',
                '-p',
                '29418',
                'gerrit',
                'review',
                '--project project',
                "--message 'bla'",
                '--label Verified=1',
                'revision',
            ],
            env=None,
        )

        # <=2.5 uses other syntax
        gsp.processVersion(parse_version("2.4"), lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.send_code_review("project", "revision", "bla", {'Verified': 1})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            [
                'ssh',
                '-o',
                'BatchMode=yes',
                'user@serv',
                '-p',
                '29418',
                'gerrit',
                'review',
                '--project project',
                "--message 'bla'",
                '--verified 1',
                'revision',
            ],
            env=None,
        )

        # now test the notify argument, even though _gerrit_notify
        # is private, work around that
        gsp._gerrit_notify = 'OWNER'
        gsp.processVersion(parse_version('2.6'), lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.send_code_review('project', 'revision', "bla", {'Verified': 1})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            [
                'ssh',
                '-o',
                'BatchMode=yes',
                'user@serv',
                '-p',
                '29418',
                'gerrit',
                'review',
                '--project project',
                '--notify OWNER',
                "--message 'bla'",
                '--label Verified=1',
                'revision',
            ],
            env=None,
        )

        # gerrit versions <= 2.5 uses other syntax
        gsp.processVersion(parse_version('2.4'), lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.send_code_review('project', 'revision', "bla", {'Verified': 1})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            [
                'ssh',
                '-o',
                'BatchMode=yes',
                'user@serv',
                '-p',
                '29418',
                'gerrit',
                'review',
                '--project project',
                '--notify OWNER',
                "--message 'bla'",
                '--verified 1',
                'revision',
            ],
            env=None,
        )

        gsp.processVersion(parse_version("2.13"), lambda: None)
        spawnSkipFirstArg = Mock()
        yield gsp.send_code_review("project", "revision", "bla", {'Verified': 1})
        spawnSkipFirstArg.assert_called_once_with(
            'ssh',
            [
                'ssh',
                '-o',
                'BatchMode=yes',
                'user@serv',
                '-p',
                '29418',
                'gerrit',
                'review',
                '--project project',
                '--tag autogenerated:buildbot',
                '--notify OWNER',
                "--message 'bla'",
                '--label Verified=1',
                'revision',
            ],
            env=None,
        )

    @defer.inlineCallbacks
    def test_callWithVersion_bytes_output(self):
        gsp = yield self.setupGerritStatusPushSimple()
        exp_argv = ['ssh', '-o', 'BatchMode=yes', 'user@serv', '-p', '29418', 'gerrit', 'version']

        def spawnProcess(pp, cmd, argv, env):
            self.assertEqual([cmd, argv], [exp_argv[0], exp_argv])
            pp.errReceived(b'test stderr\n')
            pp.outReceived(b'gerrit version 2.14\n')
            pp.outReceived(b'(garbage that should not cause a crash)\n')
            so = error.ProcessDone(None)
            pp.processEnded(failure.Failure(so))

        self.patch(reactor, 'spawnProcess', spawnProcess)
        gsp.callWithVersion(lambda: self.assertEqual(gsp.gerrit_version, parse_version('2.14')))

    def test_name_as_class_attribute(self):
        class FooStatusPush(GerritStatusPush):
            name = 'foo'

        reporter = FooStatusPush('gerrit.server.com', 'password')
        self.assertEqual(reporter.name, 'foo')

    def test_name_as_kwarg(self):
        reporter = GerritStatusPush('gerrit.server.com', 'password', name='foo')
        self.assertEqual(reporter.name, 'foo')

    def test_default_name(self):
        reporter = GerritStatusPush('gerrit.server.com', 'password')
        self.assertEqual(reporter.name, 'GerritStatusPush')

    @defer.inlineCallbacks
    def test_extract_project_revision(self):
        self.insert_test_data([SUCCESS], SUCCESS)
        res = yield utils.getDetailsForBuildset(self.master, 98, want_properties=True)
        report = {"builds": res["builds"], "buildset": res["buildset"]}

        project, revision = yield extract_project_revision(self.master, report)
        self.assertEqual(project, "testProject")
        self.assertEqual(revision, "d34db33fd43db33f")

    @defer.inlineCallbacks
    def test_extract_project_revision_no_build(self):
        self.insert_test_data([], SUCCESS)
        self.db.insert_test_data([
            fakedb.BuildsetProperty(
                buildsetid=98, property_name="event.change.id", property_value='["12345", "fakedb"]'
            ),
            fakedb.BuildsetProperty(
                buildsetid=98,
                property_name="event.change.project",
                property_value='["project1", "fakedb"]',
            ),
            fakedb.BuildsetProperty(
                buildsetid=98,
                property_name="event.patchSet.revision",
                property_value='["abcdabcd", "fakedb"]',
            ),
        ])
        res = yield utils.getDetailsForBuildset(self.master, 98, want_properties=True)
        report = {"builds": res["builds"], "buildset": res["buildset"]}

        project, revision = yield extract_project_revision(self.master, report)
        self.assertEqual(project, "project1")
        self.assertEqual(revision, "abcdabcd")
