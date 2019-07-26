from __future__ import absolute_import
from __future__ import print_function

from future.utils import string_types

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.reporters.utils import getDetailsForBuild
from buildbot.process.results import statusToString
from buildbot.util.service import BuildbotService

from telegram import Bot

class TelegramStatus(BuildbotService):
    name = "Telegram"

    def checkConfig(self, auth_token, chat_id, **kwargs):
        if not isinstance(auth_token, string_types):
            config.error('auth_token must be a string')

    @defer.inlineCallbacks
    def reconfigService(self, auth_token, chat_id, **kwargs):
        yield BuildbotService.reconfigService(self, **kwargs)

        self.auth_token = auth_token
        self.chat_id = chat_id
        self.bot = Bot(token=self.auth_token)

    @defer.inlineCallbacks
    def startService(self):
        yield BuildbotService.startService(self)

        startConsuming = self.master.mq.startConsuming
        self._buildCompleteConsumer = yield startConsuming(
            self.buildFinished,
            ('builds', None, 'finished'))

        self._buildStartedConsumer = yield startConsuming(
            self.buildStarted,
            ('builds', None, 'new'))

    def stopService(self):
        self._buildCompleteConsumer.stopConsuming()
        self._buildStartedConsumer.stopConsuming()

    def buildStarted(self, key, build):
        return self.getMoreInfoAndSend(build, key[2])

    def buildFinished(self, key, build):
        return self.getMoreInfoAndSend(build, key[2])

    @defer.inlineCallbacks
    def getMoreInfoAndSend(self, build, key):
        yield getDetailsForBuild(self.master, build)
        yield self.send(build, key)

    def getMessage(self, build, event_name):
        event_messages = {
            'new': 'Buildbot started build %s here: %s' % (build['builder']['name'], build['url']),
            'finished': 'Buildbot finished build %s with result %s here: %s'
                        % (build['builder']['name'], statusToString(build['results']), build['url'])
        }
        return event_messages.get(event_name, '')

    def send(self, build, key):
        data = self.getMessage(build, key)
        message = "{0}".format(data)
        self.bot.send_message(chat_id=self.chat_id, text=message)
