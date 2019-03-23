import json
import jwt
import time
import urllib.parse

from twisted.internet import defer

from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.logger import Logger

log = Logger()


class GCEError(RuntimeError):
    def __init__(self, response_json, url=None):
        message = response_json['error']['message']
        if url is not None:
            message = "{0}: {1}".format(url, message)

        RuntimeError.__init__(self, message)
        self.json = response_json
        self.reason = response_json.get('error')


class GCEClientService(HTTPClientService):
    name = "GCEClientService"

    def __init__(self, scopes, sa_credentials, project=None, zone=None, instance=None):
        HTTPClientService.__init__(self, "https://www.googleapis.com")
        self.sa_credentials = sa_credentials
        self.scopes = scopes
        self.project = project
        self.zone = zone
        self.instance = instance

        self.token = None
        self.tokenExpiry = 0

    @defer.inlineCallbacks
    def getBearerToken(self):
        if time.time() < self.tokenExpiry:
            return self.token

        now = time.time()
        exp = now + 3600

        sa_credentials = yield self.renderSecrets(self.sa_credentials)

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

    def zoneEndpoint(self, method=None):
        base = "/compute/v1/projects/{0}/zones/{1}".format(
            self.project, self.zone)
        if method:
            return "{0}/{1}".format(base, method)
        else:
            return base

    def instanceEndpoint(self, method=None):
        rel = "instances/{0}".format(self.instance)
        if method:
            rel = "{0}/{1}".format(rel, method)
        return self.zoneEndpoint(rel)

    def getInstanceState(self, fields=None):
        params = {}
        if fields is not None:
            params = {'fields': fields}

        return self.validateRes(
            self.get(self.instanceEndpoint(), params=params))

    def instanceStart(self):
        return self.validateRes(self.post(self.instanceEndpoint("start")))

    def instanceStop(self):
        return self.validateRes(self.post(self.instanceEndpoint("stop")))

    def createDisk(self, image=None, name=None, type=None):
        return self.validateRes(self.post(self.zoneEndpoint("disks"),
            json={
                "sourceImage": "projects/{0}/global/images/{1}".format(
                    self.project, image),
                "name": name,
                "type": "projects/{0}/zones/{1}/diskTypes/{2}".format(
                    self.project, self.zone, type)
            }
        ))

    def attachDisk(self, name=None, boot=True, index=0):
        return self.validateRes(self.post(self.instanceEndpoint("attachDisk"),
            json={
                "boot": boot,
                "source": self.zoneEndpoint("disks/{0}".format(name)),
                "deviceName": name,
                "index": index
            }
        ))

    def detachDisk(self, name):
        return self.validateRes(self.post(self.instanceEndpoint("detachDisk"),
            params={"deviceName": name}
        ))

    def deleteDisk(self, disk_name):
        return self.validateRes(self.delete(
            "{0}/disks/{1}".format(self.zoneEndpoint(), disk_name)))

    def setMetadata(self, fingerprint=None, items=[]):
        return self.validateRes(self.post(self.instanceEndpoint("setMetadata"),
            json={
                "fingerprint": fingerprint,
                "items": items,
                "kind": "compute#metadata"
            }
        ))

    @defer.inlineCallbacks
    def waitInstanceState(self, desiredState):
        state = yield self.getInstanceState(fields='status')
        while state['status'] != desiredState:
            time.sleep(0.1)
            state = yield self.validateRes(self.getInstanceState(fields='status'))

    @defer.inlineCallbacks
    def waitForOperation(self, op):
        op = yield op
        while op['status'] != 'DONE':
            time.sleep(0.1)
            op = self.get(op['selfLink'])
            op = yield self.validateRes(op)

        if 'error' in op:
            raise GCEError(op['error'])

    @defer.inlineCallbacks
    def validateRes(self, res, url=None):
        try:
            res = yield res
            res_json = yield res.json()
        except json.decoder.JSONDecodeError:
            message = yield res.content()
            res_json = {'error': {'message': message}}
            raise GCEError(res_json, url=url)

        if res.code not in (200, 201, 202):
            raise GCEError(res_json, url=url)
        return defer.returnValue(res_json)
