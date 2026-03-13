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

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import Mock

from dateutil.tz import tzutc
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.plugins import util
from buildbot.process.builder import Builder
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.bitbucketserver import HTTP_CREATED
from buildbot.reporters.bitbucketserver import HTTP_PROCESSED
from buildbot.reporters.bitbucketserver import BitbucketServerCoreAPIStatusPush
from buildbot.reporters.bitbucketserver import BitbucketServerPRCommentPush
from buildbot.reporters.bitbucketserver import BitbucketServerStatusPush
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.generators.buildset import BuildSetStatusGenerator
from buildbot.reporters.message import MessageFormatter
from buildbot.reporters.message import MessageFormatterRenderable
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.reporter import ReporterTestMixin

if TYPE_CHECKING:
    from buildbot.reporters.generators.utils import BuildStatusGeneratorMixin
    from buildbot.util.twisted import InlineCallbacksType

HTTP_NOT_FOUND = 404


class TestException(Exception):
    pass


class TestBitbucketServerStatusPush(
    TestReactorMixin, ConfigErrorsMixin, unittest.TestCase, ReporterTestMixin, LoggingMixin
):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)
        yield self.master.startService()

    @defer.inlineCallbacks
    def setupReporter(self, **kwargs: Any) -> InlineCallbacksType[None]:
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, 'serv', auth=('username', 'passwd'), debug=None, verify=None
        )
        self.sp = BitbucketServerStatusPush(
            "serv", Interpolate("username"), Interpolate("passwd"), **kwargs
        )
        yield self.sp.setServiceParent(self.master)
        self.addCleanup(self.master.stopService)

    @defer.inlineCallbacks
    def _check_start_and_finish_build(self, build: dict[str, Any]) -> InlineCallbacksType[None]:
        self._http.expect(
            'post',
            '/rest/build-status/1.0/commits/d34db33fd43db33f',
            json={
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'state': 'INPROGRESS',
                'key': 'Builder0',
                'description': 'Build started.',
            },
            code=HTTP_PROCESSED,
        )
        self._http.expect(
            'post',
            '/rest/build-status/1.0/commits/d34db33fd43db33f',
            json={
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'state': 'SUCCESSFUL',
                'key': 'Builder0',
                'description': 'Build done.',
            },
            code=HTTP_PROCESSED,
        )
        self._http.expect(
            'post',
            '/rest/build-status/1.0/commits/d34db33fd43db33f',
            json={
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'state': 'FAILED',
                'key': 'Builder0',
                'description': 'Build done.',
            },
        )
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        build['complete'] = True
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        build['results'] = FAILURE
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_basic(self) -> InlineCallbacksType[None]:
        self.setupReporter()
        build = yield self.insert_build_finished(SUCCESS)
        yield self._check_start_and_finish_build(build)

    @defer.inlineCallbacks
    def test_setting_options(self) -> InlineCallbacksType[None]:
        generator = BuildStartEndStatusGenerator(
            start_formatter=MessageFormatterRenderable('Build started.'),
            end_formatter=MessageFormatterRenderable('Build finished.'),
        )

        self.setupReporter(statusName='Build', generators=[generator])
        build = yield self.insert_build_finished(SUCCESS)
        self._http.expect(
            'post',
            '/rest/build-status/1.0/commits/d34db33fd43db33f',
            json={
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'state': 'INPROGRESS',
                'key': 'Builder0',
                'name': 'Build',
                'description': 'Build started.',
            },
            code=HTTP_PROCESSED,
        )
        self._http.expect(
            'post',
            '/rest/build-status/1.0/commits/d34db33fd43db33f',
            json={
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'state': 'SUCCESSFUL',
                'key': 'Builder0',
                'name': 'Build',
                'description': 'Build finished.',
            },
            code=HTTP_PROCESSED,
        )
        self._http.expect(
            'post',
            '/rest/build-status/1.0/commits/d34db33fd43db33f',
            json={
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'state': 'FAILED',
                'key': 'Builder0',
                'name': 'Build',
                'description': 'Build finished.',
            },
            code=HTTP_PROCESSED,
        )
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        build['complete'] = True
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        build['results'] = FAILURE
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_error(self) -> InlineCallbacksType[None]:
        self.setupReporter()
        build = yield self.insert_build_finished(SUCCESS)
        self._http.expect(
            'post',
            '/rest/build-status/1.0/commits/d34db33fd43db33f',
            json={
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'state': 'INPROGRESS',
                'key': 'Builder0',
                'description': 'Build started.',
            },
            code=HTTP_NOT_FOUND,
            content_json={
                "error_description": "This commit is unknown to us",
                "error": "invalid_commit",
            },
        )
        build['complete'] = False
        self.setUpLogging()
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('404: Unable to send Bitbucket Server status')

    @defer.inlineCallbacks
    def test_basic_with_no_revision(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        self.reporter_test_revision = None

        build = yield self.insert_build_finished(SUCCESS)

        self.setUpLogging()
        # we don't expect any request
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged("Unable to get the commit hash")
        build['complete'] = True
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        build['results'] = FAILURE
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]


class TestBitbucketServerCoreAPIStatusPush(
    ConfigErrorsMixin, TestReactorMixin, unittest.TestCase, ReporterTestMixin, LoggingMixin
):
    @defer.inlineCallbacks
    def setupReporter(self, token: str | None = None, **kwargs: Any) -> InlineCallbacksType[None]:
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

        def setup_properties(props: Properties) -> defer.Deferred[None]:
            props.setProperty("buildername", "Builder0", "Builder")
            return defer.succeed(None)

        builder = Mock(spec=Builder)
        builder.master = self.master
        builder.name = "Builder0"
        builder.setup_properties = setup_properties
        self.master.botmaster.getBuilderById = Mock(return_value=builder)

        http_headers = {} if token is None else {'Authorization': 'Bearer tokentoken'}
        http_auth = ('username', 'passwd') if token is None else None

        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, 'serv', auth=http_auth, headers=http_headers, debug=None, verify=None
        )

        auth = (Interpolate("username"), Interpolate("passwd")) if token is None else None

        self.sp = BitbucketServerCoreAPIStatusPush("serv", token=token, auth=auth, **kwargs)
        yield self.sp.setServiceParent(self.master)
        yield self.master.startService()

        @defer.inlineCallbacks
        def cleanup() -> InlineCallbacksType[None]:
            if self.master.running:
                yield self.master.stopService()

        self.addCleanup(cleanup)

    def setUp(self) -> None:
        self.master = None

    @defer.inlineCallbacks
    def _check_start_and_finish_build(
        self, build: dict[str, Any], parentPlan: bool = False, epoch: bool = False
    ) -> InlineCallbacksType[None]:
        _name = "Builder_parent #1 \u00bb Builder0 #0" if parentPlan else "Builder0 #0"
        _parent = "Builder_parent" if parentPlan else "Builder0"

        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': _name,
                'description': 'Build started.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'refs/heads/master',
                'buildNumber': '0',
                'state': 'INPROGRESS',
                'parent': _parent,
                'duration': None,
                'testResults': None,
            },
            code=HTTP_PROCESSED,
        )
        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': _name,
                'description': 'Build done.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'refs/heads/master',
                'buildNumber': '0',
                'state': 'SUCCESSFUL',
                'parent': _parent,
                'duration': 10000,
                'testResults': None,
            },
            code=HTTP_PROCESSED,
        )
        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': _name,
                'description': 'Build done.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'refs/heads/master',
                'buildNumber': '0',
                'state': 'FAILED',
                'parent': _parent,
                'duration': 10000,
                'testResults': None,
            },
            code=HTTP_PROCESSED,
        )
        if epoch:
            build['started_at'] = 1554161913
        else:
            build['started_at'] = datetime.datetime(2019, 4, 1, 23, 38, 33, 154354, tzinfo=tzutc())
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        if epoch:
            build["complete_at"] = 1554161923
        else:
            build["complete_at"] = datetime.datetime(2019, 4, 1, 23, 38, 43, 154354, tzinfo=tzutc())
        build['complete'] = True
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        build['results'] = FAILURE
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_buildrequest(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        buildrequest = yield self.insert_buildrequest_new()

        _name = "Builder0 #(build request)"
        _parent = "Builder0"
        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': _name,
                'description': 'Build pending.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/buildrequests/11',
                'ref': 'refs/heads/master',
                'buildNumber': '',
                'state': 'INPROGRESS',
                'parent': _parent,
                'duration': None,
                'testResults': None,
            },
            code=HTTP_PROCESSED,
        )
        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': _name,
                'description': 'Build pending.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/buildrequests/11',
                'ref': 'refs/heads/master',
                'buildNumber': '',
                'state': 'FAILED',
                'parent': _parent,
                'duration': None,
                'testResults': None,
            },
            code=HTTP_PROCESSED,
        )

        yield self.sp._got_event(('buildrequests', 11, 'new'), buildrequest)  # type: ignore[arg-type]
        yield self.sp._got_event(('buildrequests', 11, 'cancel'), buildrequest)  # type: ignore[arg-type]

    def test_config_no_base_url(self) -> None:
        with self.assertRaisesConfigError("Parameter base_url has to be given"):
            BitbucketServerCoreAPIStatusPush(base_url=None)

    def test_config_auth_and_token_mutually_exclusive(self) -> None:
        with self.assertRaisesConfigError(
            "Only one authentication method can be given (token or auth)"
        ):
            BitbucketServerCoreAPIStatusPush("serv", token="x", auth=("username", "passwd"))

    @defer.inlineCallbacks
    def test_basic(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        build = yield self.insert_build_finished(SUCCESS)
        yield self._check_start_and_finish_build(build)

    @defer.inlineCallbacks
    def test_basic_epoch(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        build = yield self.insert_build_finished(SUCCESS)
        yield self._check_start_and_finish_build(build, epoch=True)

    @defer.inlineCallbacks
    def test_with_parent(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        build = yield self.insert_build_finished(SUCCESS, parent_plan=True)
        yield self._check_start_and_finish_build(build, parentPlan=True)

    @defer.inlineCallbacks
    def test_with_token(self) -> InlineCallbacksType[None]:
        yield self.setupReporter(token='tokentoken')
        build = yield self.insert_build_finished(SUCCESS)
        yield self._check_start_and_finish_build(build)

    @defer.inlineCallbacks
    def test_error_setup_status(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()

        @defer.inlineCallbacks
        def raise_deferred_exception(**kwargs: Any) -> InlineCallbacksType[None]:
            raise TestException()

        self.sp.createStatus = Mock(side_effect=raise_deferred_exception)  # type: ignore[method-assign]
        build = yield self.insert_build_finished(SUCCESS)
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]

        self.assertEqual(len(self.flushLoggedErrors(TestException)), 1)

    @defer.inlineCallbacks
    def test_error(self) -> InlineCallbacksType[None]:
        self.setupReporter()
        build = yield self.insert_build_finished(SUCCESS)
        self.setUpLogging()
        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': 'Builder0 #0',
                'description': 'Build started.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'refs/heads/master',
                'buildNumber': '0',
                'state': 'INPROGRESS',
                'parent': 'Builder0',
                'duration': None,
                'testResults': None,
            },
            code=HTTP_NOT_FOUND,
        )
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('404: Unable to send Bitbucket Server status')

    @defer.inlineCallbacks
    def test_with_full_ref(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        self.reporter_test_branch = "refs/heads/master"
        build = yield self.insert_build_finished(SUCCESS)

        yield self._check_start_and_finish_build(build)

    @defer.inlineCallbacks
    def test_with_no_ref(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()

        self.reporter_test_branch = None
        build = yield self.insert_build_finished(SUCCESS)

        self.setUpLogging()
        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': 'Builder0 #0',
                'description': 'Build started.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': None,
                'buildNumber': '0',
                'state': 'INPROGRESS',
                'parent': 'Builder0',
                'duration': None,
                'testResults': None,
            },
            code=HTTP_PROCESSED,
        )
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged("WARNING: Unable to resolve ref for SSID: 234.")

    @defer.inlineCallbacks
    def test_with_no_revision(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()

        self.reporter_test_revision = None
        build = yield self.insert_build_finished(SUCCESS)

        self.setUpLogging()
        # we don't expect any request
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged("Unable to get the commit hash for SSID: 234")

    @defer.inlineCallbacks
    def test_with_no_repo(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()

        self.reporter_test_repo = ''
        build = yield self.insert_build_finished(SUCCESS)

        self.setUpLogging()
        # we don't expect any request
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged("Unable to parse repository info from '' for SSID: 234")

    @defer.inlineCallbacks
    def test_with_renderers(self) -> InlineCallbacksType[None]:
        @util.renderer
        def r_testresults(props: Any) -> Any:
            return {
                "failed": props.getProperty("unittests_failed", 0),
                "skipped": props.getProperty("unittests_skipped", 0),
                "successful": props.getProperty("unittests_successful", 0),
            }

        @util.renderer
        def r_duration(props: Any) -> Any:
            return props.getProperty("unittests_runtime")

        yield self.setupReporter(
            statusName=Interpolate("%(prop:plan_name)s"),
            statusSuffix=Interpolate(" [%(prop:unittests_os)s]"),
            buildNumber=Interpolate('100'),
            ref=Interpolate("%(prop:branch)s"),
            parentName=Interpolate("%(prop:master_plan)s"),
            testResults=r_testresults,
            duration=r_duration,
        )

        self.reporter_test_props['unittests_failed'] = 0
        self.reporter_test_props['unittests_skipped'] = 2
        self.reporter_test_props['unittests_successful'] = 3
        self.reporter_test_props['unittests_runtime'] = 50000
        self.reporter_test_props['unittests_os'] = "win10"
        self.reporter_test_props['plan_name'] = "Unittests"
        self.reporter_test_props['master_plan'] = "Unittests-master"
        build = yield self.insert_build_finished(SUCCESS)

        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': 'Unittests [win10]',
                'description': 'Build done.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': "refs/pull/34/merge",
                'buildNumber': '100',
                'state': 'SUCCESSFUL',
                'parent': 'Unittests-master',
                'duration': 50000,
                'testResults': {'failed': 0, 'skipped': 2, 'successful': 3},
            },
            code=HTTP_PROCESSED,
        )
        build['complete'] = True
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_with_test_results(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()

        self.reporter_test_props['tests_skipped'] = 2
        self.reporter_test_props['tests_successful'] = 3
        build = yield self.insert_build_finished(SUCCESS)

        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': 'Builder0 #0',
                'description': 'Build done.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': 'refs/heads/master',
                'buildNumber': '0',
                'state': 'SUCCESSFUL',
                'parent': 'Builder0',
                'duration': 10000,
                'testResults': {'failed': 0, 'skipped': 2, 'successful': 3},
            },
            code=HTTP_PROCESSED,
        )
        build['started_at'] = datetime.datetime(2019, 4, 1, 23, 38, 33, 154354, tzinfo=tzutc())
        build["complete_at"] = datetime.datetime(2019, 4, 1, 23, 38, 43, 154354, tzinfo=tzutc())
        build['complete'] = True
        yield self.sp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_verbose(self) -> InlineCallbacksType[None]:
        yield self.setupReporter(verbose=True)
        build = yield self.insert_build_finished(SUCCESS)
        self.setUpLogging()
        self._http.expect(
            'post',
            '/rest/api/1.0/projects/example.org/repos/repo/commits/d34db33fd43db33f/builds',
            json={
                'name': 'Builder0 #0',
                'description': 'Build started.',
                'key': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'ref': "refs/heads/master",
                'buildNumber': '0',
                'state': 'INPROGRESS',
                'parent': 'Builder0',
                'duration': None,
                'testResults': None,
            },
            code=HTTP_PROCESSED,
        )
        build['complete'] = False
        yield self.sp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('Sending payload:')
        self.assertLogged('Status "INPROGRESS" sent for example.org/repo d34db33fd43db33f')


UNICODE_BODY = "body: \u00e5\u00e4\u00f6 text"
EXPECTED_API = '/rest/api/1.0/projects/PRO/repos/myrepo/pull-requests/20/comments'
PR_URL = "http://example.com/projects/PRO/repos/myrepo/pull-requests/20"


class TestBitbucketServerPRCommentPush(
    TestReactorMixin, unittest.TestCase, ReporterTestMixin, LoggingMixin
):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)
        yield self.master.startService()
        self.addCleanup(self.master.stopService)

    @defer.inlineCallbacks
    def setupReporter(
        self,
        verbose: bool = True,
        generator_class: type[BuildStatusGeneratorMixin] = BuildStatusGenerator,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, 'serv', auth=('username', 'passwd'), debug=None, verify=None
        )

        formatter = Mock(spec=MessageFormatter)
        formatter.format_message_for_build.return_value = {
            "body": UNICODE_BODY,
            "type": "text",
            "subject": "subject",
            "extra_info": None,
        }
        formatter.want_properties = True
        formatter.want_steps = False
        formatter.want_logs = False
        formatter.want_logs_content = False

        generator = generator_class(message_formatter=formatter)  # type: ignore[call-arg]

        self.cp = BitbucketServerPRCommentPush(
            "serv",
            Interpolate("username"),
            Interpolate("passwd"),
            verbose=verbose,
            generators=[generator],
            **kwargs,
        )
        yield self.cp.setServiceParent(self.master)

    @defer.inlineCallbacks
    def setupBuildResults(
        self, buildResults: int | None, set_pr: bool = True
    ) -> InlineCallbacksType[Any]:
        yield super().insert_test_data([buildResults], buildResults)
        build = yield self.master.data.get(('builds', 20))
        if set_pr:
            yield self.master.db.builds.setBuildProperty(20, "pullrequesturl", PR_URL, "test")
        return build

    @defer.inlineCallbacks
    def test_reporter_basic(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        build = yield self.setupBuildResults(SUCCESS)
        self._http.expect("post", EXPECTED_API, json={"text": UNICODE_BODY}, code=HTTP_CREATED)
        build["complete"] = True
        self.setUpLogging()
        yield self.cp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        self.assertLogged(f'Comment sent to {PR_URL}')

    @defer.inlineCallbacks
    def test_reporter_basic_without_logging(self) -> InlineCallbacksType[None]:
        yield self.setupReporter(verbose=False)
        build = yield self.setupBuildResults(SUCCESS)
        self._http.expect("post", EXPECTED_API, json={"text": UNICODE_BODY}, code=HTTP_CREATED)
        build["complete"] = True
        self.setUpLogging()
        yield self.cp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

        self.assertNotLogged(f'Comment sent to {PR_URL}')

    @defer.inlineCallbacks
    def test_reporter_without_pullrequest(self) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        build = yield self.setupBuildResults(SUCCESS, set_pr=False)
        build["complete"] = True
        # we don't expect any request
        yield self.cp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_reporter_with_buildset(self) -> InlineCallbacksType[None]:
        yield self.setupReporter(generator_class=BuildSetStatusGenerator)
        yield self.setupBuildResults(SUCCESS)
        buildset = yield self.get_inserted_buildset()
        self._http.expect("post", EXPECTED_API, json={"text": UNICODE_BODY}, code=HTTP_CREATED)
        yield self.cp._got_event(("buildsets", 98, "complete"), buildset)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_reporter_logs_error_code_and_content_on_invalid_return_code(
        self,
    ) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        build = yield self.setupBuildResults(SUCCESS)

        http_error_code = 500
        error_body = {"errors": [{"message": "A dataXXXbase error has occurred."}]}

        self._http.expect(
            "post",
            EXPECTED_API,
            json={"text": UNICODE_BODY},
            code=http_error_code,
            content_json=error_body,
        )
        self.setUpLogging()
        build['complete'] = True
        yield self.cp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

        self.assertLogged(f"^{http_error_code}: Unable to send a comment: ")
        self.assertLogged("A dataXXXbase error has occurred")

    @defer.inlineCallbacks
    def test_reporter_logs_error_code_without_content_on_invalid_return_code(
        self,
    ) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        build = yield self.setupBuildResults(SUCCESS)
        http_error_code = 503
        self._http.expect("post", EXPECTED_API, json={"text": UNICODE_BODY}, code=http_error_code)
        self.setUpLogging()
        build['complete'] = True
        yield self.cp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        self.assertLogged(f"^{http_error_code}: Unable to send a comment: ")

    @defer.inlineCallbacks
    def test_reporter_does_not_log_return_code_on_valid_return_code(
        self,
    ) -> InlineCallbacksType[None]:
        yield self.setupReporter()
        build = yield self.setupBuildResults(SUCCESS)
        http_code = 201
        self._http.expect("post", EXPECTED_API, json={"text": UNICODE_BODY}, code=http_code)
        self.setUpLogging()
        build['complete'] = True
        yield self.cp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        self.assertNotLogged(f"^{http_code}:")
