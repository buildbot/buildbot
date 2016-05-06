from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.process.results import statusToString
from buildbot.reporters import utils
from buildbot.reporters.http import HttpStatusPushBase


class HipChatStatusPush(HttpStatusPushBase):
    name = "HipChatStatusPush"

    def checkConfig(self, auth_token, endpoint="https://api.hipchat.com",
                    builder_room_map=None, builder_user_map=None,
                    event_messages=None, **kwargs):
        if not isinstance(auth_token, basestring):
            config.error('auth_token must be a string')
        if not isinstance(endpoint, basestring):
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
        self.auth_token = auth_token
        self.endpoint = endpoint
        self.builder_room_map = builder_room_map
        self.builder_user_map = builder_user_map
        self.user_notify = '%sv2/user/%s/message?auth_token=%s'
        self.room_notify = '%sv2/room/%s/notification?auth_token=%s'

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

    # use this as an extension point to inject extra parameters into your postData
    def getExtraParams(self, build, event_name):
        return {}

    @defer.inlineCallbacks
    def send(self, build, key):
        postData = yield self.getBuildDetailsAndSendMessage(build, key)
        if not postData or 'message' not in postData or not postData['message']:
            return

        if not self.endpoint.endswith('/'):
            self.endpoint += '/'

        urls = []
        if 'id_or_email' in postData:
            urls.append(self.user_notify % (self.endpoint, postData.pop('id_or_email'), self.auth_token))
        if 'room_id_or_name' in postData:
            urls.append(self.room_notify % (self.endpoint, postData.pop('room_id_or_name'), self.auth_token))

        if urls:
            for url in urls:
                response = yield self.session.post(url, postData)
                if response.status_code != 200:
                    log.msg("%s: unable to upload status: %s" %
                            (response.status_code, response.content))
