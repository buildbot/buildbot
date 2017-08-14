from __future__ import absolute_import
from __future__ import print_function
from future.utils import string_types

from twisted.internet import defer

from buildbot import config
from buildbot.process.results import statusToString
from buildbot.reporters import utils
from buildbot.reporters.http import HttpStatusPushBase
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger

log = Logger()

HOSTED_BASE_URL = "https://api.hipchat.com"


class HipChatStatusPush(HttpStatusPushBase):
    name = "HipChatStatusPush"

    def checkConfig(self, auth_token, endpoint=HOSTED_BASE_URL,
                    builder_room_map=None, builder_user_map=None,
                    event_messages=None, **kwargs):
        if not isinstance(auth_token, string_types):
            config.error('auth_token must be a string')
        if not isinstance(endpoint, string_types):
            config.error('endpoint must be a string')
        if builder_room_map and not isinstance(builder_room_map, dict):
            config.error('builder_room_map must be a dict')
        if builder_user_map and not isinstance(builder_user_map, dict):
            config.error('builder_user_map must be a dict')

    @defer.inlineCallbacks
    def reconfigService(self, auth_token, endpoint="https://api.hipchat.com",
                        builder_room_map=None, builder_user_map=None,
                        event_messages=None, **kwargs):
        yield HttpStatusPushBase.reconfigService(self, **kwargs)
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, endpoint,
            debug=self.debug, verify=self.verify)

        self.auth_token = auth_token
        self.builder_room_map = builder_room_map
        self.builder_user_map = builder_user_map

    @defer.inlineCallbacks
    def buildStarted(self, key, build):
        yield self.send(build, key[2])

    @defer.inlineCallbacks
    def buildFinished(self, key, build):
        yield self.send(build, key[2])

    @defer.inlineCallbacks
    def getBuildDetailsAndSendMessage(self, build, key):
        yield utils.getDetailsForBuild(self.master, build, **self.neededDetails)
        postData = yield self.getRecipientList(build, key)
        postData['message'] = yield self.getMessage(build, key)
        extra_params = yield self.getExtraParams(build, key)
        postData.update(extra_params)
        defer.returnValue(postData)

    def getRecipientList(self, build, event_name):
        result = {}
        builder_name = build['builder']['name']
        if self.builder_user_map and builder_name in self.builder_user_map:
            result['id_or_email'] = self.builder_user_map[builder_name]
        if self.builder_room_map and builder_name in self.builder_room_map:
            result['room_id_or_name'] = self.builder_room_map[builder_name]
        return result

    def getMessage(self, build, event_name):
        event_messages = {
            'new': 'Buildbot started build %s here: %s' % (build['builder']['name'], build['url']),
            'finished': 'Buildbot finished build %s with result %s here: %s'
                        % (build['builder']['name'], statusToString(build['results']), build['url'])
        }
        return event_messages.get(event_name, '')

    # use this as an extension point to inject extra parameters into your
    # postData
    def getExtraParams(self, build, event_name):
        return {}

    @defer.inlineCallbacks
    def send(self, build, key):
        postData = yield self.getBuildDetailsAndSendMessage(build, key)
        if not postData or 'message' not in postData or not postData['message']:
            return

        urls = []
        if 'id_or_email' in postData:
            urls.append('/v2/user/{}/message'.format(postData.pop('id_or_email')))
        if 'room_id_or_name' in postData:
            urls.append('/v2/room/{}/notification'.format(postData.pop('room_id_or_name')))

        for url in urls:
            response = yield self._http.post(url, params=dict(auth_token=self.auth_token), json=postData)
            if response.code != 200:
                content = yield response.content()
                log.error("{code}: unable to upload status: {content}",
                          code=response.code, content=content)
