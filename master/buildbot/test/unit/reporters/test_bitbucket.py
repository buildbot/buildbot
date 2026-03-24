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

from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.bitbucket import _BASE_URL
from buildbot.reporters.bitbucket import _OAUTH_URL
from buildbot.reporters.bitbucket import BitbucketStatusPush
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.message import MessageFormatter
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.reporter import ReporterTestMixin
from buildbot.util import httpclientservice

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestBitbucketStatusPush(
    TestReactorMixin, ConfigErrorsMixin, ReporterTestMixin, LoggingMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()

        self.setup_reporter_test()
        self.reporter_test_repo = 'https://example.org/user/repo'

        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

        self._http = yield fakehttpclientservice.HTTPClientService.getService(self.master, self, "")
        self.httpsession = httpclientservice.HTTPSession(
            None,  # type: ignore[arg-type]
            _BASE_URL,
            auth=None,
            debug=None,
            verify=None,
        )
        self.httpsession.update_headers({'Authorization': 'Bearer foo'})

        self.oauthsession = httpclientservice.HTTPSession(
            None,  # type: ignore[arg-type]
            _OAUTH_URL,
            auth=('key', 'secret'),
            debug=None,
            verify=None,
        )

        self.bsp = BitbucketStatusPush(Interpolate('key'), Interpolate('secret'))
        yield self.bsp.setServiceParent(self.master)
        yield self.bsp.startService()
        self.addCleanup(self.bsp.stopService)

    @defer.inlineCallbacks
    def test_basic(self) -> InlineCallbacksType[None]:
        build = yield self.insert_build_new()

        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )
        self._http.expect(
            'post',
            '/user/repo/commit/d34db33fd43db33f/statuses/build',
            session=self.httpsession,
            json={
                'state': 'INPROGRESS',
                'key': '0550a051225ac4ea91a92c9c94d41dfe6fa9f428',  # sha1("Builder0")
                'name': 'Builder0',
                'description': '',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
            },
            code=201,
        )

        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )
        self._http.expect(
            'post',
            '/user/repo/commit/d34db33fd43db33f/statuses/build',
            session=self.httpsession,
            json={
                'state': 'SUCCESSFUL',
                'key': '0550a051225ac4ea91a92c9c94d41dfe6fa9f428',  # sha1("Builder0")
                'name': 'Builder0',
                'description': '',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
            },
            code=201,
        )

        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )
        self._http.expect(
            'post',
            '/user/repo/commit/d34db33fd43db33f/statuses/build',
            session=self.httpsession,
            json={
                'state': 'FAILED',
                'key': '0550a051225ac4ea91a92c9c94d41dfe6fa9f428',  # sha1("Builder0")
                'name': 'Builder0',
                'description': '',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
            },
            code=201,
        )

        yield self.bsp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]

        build['complete'] = True
        build['results'] = SUCCESS
        yield self.bsp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

        build['results'] = FAILURE
        yield self.bsp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]

    @defer.inlineCallbacks
    def test_success_return_codes(self) -> InlineCallbacksType[None]:
        build = yield self.insert_build_finished(SUCCESS)

        # make sure a 201 return code does not trigger an error
        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )
        self._http.expect(
            'post',
            '/user/repo/commit/d34db33fd43db33f/statuses/build',
            session=self.httpsession,
            json={
                'state': 'SUCCESSFUL',
                'key': '0550a051225ac4ea91a92c9c94d41dfe6fa9f428',  # sha1("Builder0")
                'name': 'Builder0',
                'description': '',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
            },
            code=201,
        )

        self.setUpLogging()
        yield self.bsp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        self.assertNotLogged('201: unable to upload Bitbucket status')

        # make sure a 200 return code does not trigger an error
        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )
        self._http.expect(
            'post',
            '/user/repo/commit/d34db33fd43db33f/statuses/build',
            session=self.httpsession,
            json={
                'state': 'SUCCESSFUL',
                'key': '0550a051225ac4ea91a92c9c94d41dfe6fa9f428',  # sha1("Builder0")
                'name': 'Builder0',
                'description': '',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
            },
            code=200,
        )

        self.setUpLogging()
        yield self.bsp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]
        self.assertNotLogged('200: unable to upload Bitbucket status')

    @defer.inlineCallbacks
    def test_unable_to_authenticate(self) -> InlineCallbacksType[None]:
        build = yield self.insert_build_new()

        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={
                "error_description": "Unsupported grant type: None",
                "error": "invalid_grant",
            },
            code=400,
        )
        self.setUpLogging()
        yield self.bsp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('400: unable to authenticate to Bitbucket')

    @defer.inlineCallbacks
    def test_unable_to_send_status(self) -> InlineCallbacksType[None]:
        build = yield self.insert_build_new()

        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )
        self._http.expect(
            'post',
            '/user/repo/commit/d34db33fd43db33f/statuses/build',
            session=self.httpsession,
            json={
                'state': 'INPROGRESS',
                'key': '0550a051225ac4ea91a92c9c94d41dfe6fa9f428',  # sha1("Builder0")
                'name': 'Builder0',
                'description': '',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
            },
            code=404,
            content_json={
                "error_description": "This commit is unknown to us",
                "error": "invalid_commit",
            },
        )
        self.setUpLogging()
        yield self.bsp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('404: unable to upload Bitbucket status')
        self.assertLogged('This commit is unknown to us')
        self.assertLogged('invalid_commit')

    @defer.inlineCallbacks
    def test_empty_repository(self) -> InlineCallbacksType[None]:
        self.reporter_test_repo = ''
        build = yield self.insert_build_new()

        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )

        self.setUpLogging()
        yield self.bsp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]
        self.assertLogged('Empty repository URL for Bitbucket status')


class TestBitbucketStatusPushProperties(
    TestReactorMixin, ConfigErrorsMixin, ReporterTestMixin, LoggingMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()

        self.setup_reporter_test()
        self.reporter_test_repo = 'https://example.org/user/repo'

        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master,
            self,
            "",
        )
        self.httpsession = httpclientservice.HTTPSession(
            None,  # type: ignore[arg-type]
            _BASE_URL,
            auth=None,
            debug=None,
            verify=None,
        )
        self.httpsession.update_headers({'Authorization': 'Bearer foo'})

        self.oauthsession = httpclientservice.HTTPSession(
            None,  # type: ignore[arg-type]
            _OAUTH_URL,
            auth=('key', 'secret'),
            debug=None,
            verify=None,
        )

        self.bsp = BitbucketStatusPush(
            Interpolate('key'),
            Interpolate('secret'),
            status_key=Interpolate("%(prop:buildername)s/%(prop:buildnumber)s"),
            status_name=Interpolate("%(prop:buildername)s-%(prop:buildnumber)s"),
            generators=[
                BuildStartEndStatusGenerator(
                    start_formatter=MessageFormatter(subject="{{ status_detected }}"),
                    end_formatter=MessageFormatter(subject="{{ summary }}"),
                )
            ],
        )
        yield self.bsp.setServiceParent(self.master)
        yield self.bsp.startService()
        self.addCleanup(self.bsp.stopService)

    @defer.inlineCallbacks
    def test_properties(self) -> InlineCallbacksType[None]:
        build = yield self.insert_build_new()

        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )
        self._http.expect(
            'post',
            '/user/repo/commit/d34db33fd43db33f/statuses/build',
            session=self.httpsession,
            json={
                'state': 'INPROGRESS',
                'key': '84f9e75c46896d56da4fd75e096d24ec62f76f33',  # sha1("Builder0/0")
                'name': 'Builder0-0',
                'description': 'not finished build',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
            },
            code=201,
        )

        self._http.expect(
            'post',
            '',
            session=self.oauthsession,
            data={'grant_type': 'client_credentials'},
            content_json={'access_token': 'foo'},
        )
        self._http.expect(
            'post',
            '/user/repo/commit/d34db33fd43db33f/statuses/build',
            session=self.httpsession,
            json={
                'state': 'SUCCESSFUL',
                'key': '84f9e75c46896d56da4fd75e096d24ec62f76f33',  # sha1("Builder0/0")
                'name': 'Builder0-0',
                'description': 'Build succeeded!',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
            },
            code=201,
        )

        yield self.bsp._got_event(('builds', 20, 'new'), build)  # type: ignore[arg-type]

        build['complete'] = True
        build['results'] = SUCCESS
        yield self.bsp._got_event(('builds', 20, 'finished'), build)  # type: ignore[arg-type]


class TestBitbucketStatusPushConfig(ConfigErrorsMixin, unittest.TestCase):
    def test_auth_error(self) -> None:
        with self.assertRaisesConfigError(
            "Either App Passwords or OAuth can be specified, not both"
        ):
            BitbucketStatusPush(oauth_key='abc', oauth_secret='abc1', auth=('user', 'pass'))


class TestBitbucketStatusPushRepoParsing(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

        self.bsp = BitbucketStatusPush(Interpolate('key'), Interpolate('secret'))
        yield self.bsp.setServiceParent(self.master)
        yield self.bsp.startService()
        self.addCleanup(self.bsp.stopService)

    def parse(self, repourl: str) -> tuple[str, ...]:
        return tuple(self.bsp.get_owner_and_repo(repourl))

    def test_parse_no_scheme(self) -> None:
        self.assertEqual(('user', 'repo'), self.parse('git@bitbucket.com:user/repo.git'))
        self.assertEqual(('user', 'repo'), self.parse('git@bitbucket.com:user/repo'))

    def test_parse_with_scheme(self) -> None:
        self.assertEqual(('user', 'repo'), self.parse('https://bitbucket.com/user/repo.git'))
        self.assertEqual(('user', 'repo'), self.parse('https://bitbucket.com/user/repo'))

        self.assertEqual(('user', 'repo'), self.parse('ssh://git@bitbucket.com/user/repo.git'))
        self.assertEqual(('user', 'repo'), self.parse('ssh://git@bitbucket.com/user/repo'))
        self.assertEqual(
            ('user', 'repo'), self.parse('https://api.bitbucket.org/2.0/repositories/user/repo')
        )
