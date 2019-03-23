# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more # details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import os
import urllib

import jwt

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.gce import GCERecorder


class TestGCEClientService(unittest.TestCase):
    def renderSecrets(self, secrets):
        return secrets

    def createService(self, project="p", zone="z", instance="i", image='im', sa_credentials={}):
        return GCERecorder(
            ['https://www.googleapis.com/auth/compute'],
            sa_credentials, project=project, zone=zone, instance=instance,
            renderer=self)

    def setUp(self):
        dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(dir, 'gce-jwtRS256.key'), 'r') as f:
            self.private_key = f.read()
        with open(os.path.join(dir, 'gce-jwtRS256.key.pub'), 'r') as f:
            self.public_key = f.read()

    @defer.inlineCallbacks
    def test_getBearerToken_acquires_the_token(self):
        service = self.createService(sa_credentials={
            'client_email': 'test@buildbot.net',
            'private_key': self.private_key
        })
        now = 45678
        expected_jwt_data = {
            "iss": "test@buildbot.net",
            "scope": "https://www.googleapis.com/auth/compute",
            "aud": "https://www.googleapis.com/oauth2/v4/token",
            "iat": now, "exp": now + 3600
        }
        expected_jwt_token = jwt.encode(expected_jwt_data, key=self.private_key, algorithm="RS256")
        expected_params = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": expected_jwt_token
        })
        service.expect('POST', '/oauth2/v4/token', data=expected_params,
            result={'token_type': 'Bearer', 'access_token': 'somethingsomething'})
        result = yield service.getBearerToken(now=now)
        self.assertEqual("somethingsomething", result)

    @defer.inlineCallbacks
    def test_getBearerToken_returns_a_still_valid_token(self):
        service = self.createService(sa_credentials={
            'client_email': 'test@buildbot.net',
            'private_key': self.private_key
        })
        now = 45678
        service.expect('POST', '/oauth2/v4/token', data=GCERecorder.IGNORE,
            result={'token_type': 'Bearer', 'access_token': 'somethingsomething'})
        yield service.getBearerToken(now=now)
        result = yield service.getBearerToken(now=now)
        self.assertEqual(result, 'somethingsomething')

    @defer.inlineCallbacks
    def test_getBearerToken_reacquires_an_expired_token(self):
        service = self.createService(sa_credentials={
            'client_email': 'test@buildbot.net',
            'private_key': self.private_key
        })
        now = 45678
        service.expect('POST', '/oauth2/v4/token', data=GCERecorder.IGNORE,
            result={'token_type': 'Bearer', 'access_token': 'somethingsomething'})
        service.expect('POST', '/oauth2/v4/token', data=GCERecorder.IGNORE,
            result={'token_type': 'Bearer', 'access_token': 'somethingsomething2'})
        yield service.getBearerToken(now=now)
        result = yield service.getBearerToken(now=now + 3600 - 59)
        self.assertEqual(result, 'somethingsomething2')
