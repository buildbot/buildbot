from twisted.internet import defer

from buildbot import config
from buildbot.reporters import utils
from buildbot.reporters.http import HttpStatusPushBase
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger

logger = Logger()


class ZulipStatusPush(HttpStatusPushBase):
    name = "ZulipStatusPush"

    def checkConfig(self, endpoint, token, stream=None, **kwargs):
        if not isinstance(endpoint, str):
            config.error("Endpoint must be a string")
        if not isinstance(token, str):
            config.error("Token must be a string")

    @defer.inlineCallbacks
    def reconfigService(self, endpoint, token, stream=None, **kwargs):
        super().reconfigService(**kwargs)
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, endpoint,
            debug=self.debug, verify=self.verify)
        self.token = token
        self.stream = stream

    def buildStarted(self, key, build):
        return self.send(build, key[2])

    def buildFinished(self, key, build):
        return self.send(build, key[2])

    @defer.inlineCallbacks
    def getBuildDetails(self, build, event):
        yield utils.getDetailsForBuild(self.master, build, wantProperties=True)
        jsondata = dict(event=event, buildid=build["buildid"], buildername=build["builder"]["name"], url=build["url"],
                        project=build["properties"]["project"][0])
        if event == "new":
            jsondata["timestamp"] = build["started_at"]
        elif event == "finished":
            jsondata["timestamp"] = build["complete_at"]
            jsondata["results"] = build["results"]
        return jsondata

    @defer.inlineCallbacks
    def send(self, build, event):
        jsondata = yield self.getBuildDetails(build, event)
        if self.stream is not None:
            url = "/api/v1/external/buildbot?api_key={}&stream={}".format(self.token, self.stream)
        else:
            url = "/api/v1/external/buildbot?api_key={}".format(self.token)
        res = yield self._http.post(url, json=jsondata)
        if res.code != 200:
            content = yield res.content()
            logger.error("{}: Error pushing build status to Zulip: {}".format(res.code, content))
