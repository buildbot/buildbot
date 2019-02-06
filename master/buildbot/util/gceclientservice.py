import json
import jwt
import time
import urllib.parse

from twisted.internet import defer

from buildbot import config
from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.logger import Logger
from buildbot.util.service import BuildbotService

log = Logger()

# this is a BuildbotService, so that it can be started and destroyed.
# this is needed to implement kubectl proxy lifecycle
class GCEClientService(HTTPClientService):
    name = "GCEClientService"

    def __init__(self, scopes, sa_credentials, renderer=None):
        HTTPClientService.__init__(self, "https://www.googleapis.com")
        self.sa_credentials = sa_credentials
        self.scopes = scopes
        self.renderer = renderer

        self.token = None
        self.tokenExpiry = 0

    @defer.inlineCallbacks
    def getBearerToken(self):
        if time.time() < self.tokenExpiry:
            return self.token

        now = time.time()
        exp = now + 3600

        if self.renderer is not None:
            sa_credentials = yield self.renderer.renderSecrets(self.sa_credentials)
        else:
            sa_credentials = self.sa_credentials

        if isinstance(sa_credentials, str):
            sa_credentials = json.loads(sa_credentials)

        data = {
            "iss": sa_credentials['client_email'],
            "scope": " ".join(self.scopes),
            "aud": "https://www.googleapis.com/oauth2/v4/token",
            "iat": now, 'exp': exp
        }
        jwt_token = jwt.encode(data, key=sa_credentials['private_key'], algorithm="RS256")

        response = yield self.post("/oauth2/v4/token",
            needToken=False, data=urllib.parse.urlencode({
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token
            }),
            headers={'Content-Type': "application/x-www-form-urlencoded"}
        )
        if response.code >= 400:
            raise Exception("Failed to get authorization token (HTTP code {0}".
                format(response.code))

        token_result = yield response.json()

        if token_result['token_type'] == 'Bearer':
            self.tokenExpiry = exp - 60
            self.token = token_result['access_token']
            return defer.returnValue(self.token)
        else:
            raise "failed to get an access token"

    @defer.inlineCallbacks
    def _prepareRequest(self, ep, kwargs):
        url, req_kwargs = HTTPClientService._prepareRequest(self, ep, kwargs)

        needToken = kwargs.pop('needToken', True)
        if needToken:
            token = yield self.getBearerToken()
            req_kwargs['headers']['Authorization'] = "Bearer {0}".format(token)

        return url, req_kwargs
