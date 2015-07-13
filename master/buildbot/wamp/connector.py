# This file is part of .  Buildbot is free software: you can
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
# Copyright  Team Members

from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.wamp import Service
from autobahn.twisted.websocket import WampWebSocketClientFactory
from autobahn.wamp.exception import TransportLost

from twisted.internet import defer
from twisted.python import failure
from twisted.python import log

from buildbot.util import service


class BuildbotWampWebSocketClientFactory(WampWebSocketClientFactory):

    def __init__(self, master, *args, **kw):
        self.master = master
        WampWebSocketClientFactory.__init__(self, *args, **kw)

    @defer.inlineCallbacks
    def clientConnectionFailed(self, connector, reason):
        print "wamp router connection failed!", reason
        yield WampWebSocketClientFactory.clientConnectionFailed(self, connector, reason)
        yield self.master.stopService()


class BuildbotWampService(Service):

    def factory(self, *args, **kwargs):
        return BuildbotWampWebSocketClientFactory(self.extra['master'], *args, **kwargs)


class MasterService(ApplicationSession, service.AsyncMultiService):

    """
    concatenation of all the wamp services of buildbot
    """

    def __init__(self, config):
        ApplicationSession.__init__(self)
        service.AsyncMultiService.__init__(self)
        self.config = config
        self.master = config.extra['master']
        self.setServiceParent(config.extra['parent'])

    @defer.inlineCallbacks
    def onJoin(self, details):
        for handler in [self] + self.services:
            yield self.register(handler)
            yield self.subscribe(handler)
        yield self.publish("org.buildbot.%s.connected" % (self.master.masterid))
        self.parent.service = self
        self.parent.serviceDeferred.callback(self)

    @defer.inlineCallbacks
    def onLeave(self, details):
        # first implementation: we skip the reconnection problem
        # Just stop the service, and crash the master. Relaunch will be done by the process manager
        yield self.master.stopService()


def make(config):

    if config:
        return MasterService(config)
    else:
        # if no config given, return a description of this WAMPlet ..
        return {'label': 'Buildbot master wamplet',
                'description': 'This contains all the wamp methods provided by a buildbot master'}


class WampConnector(service.ReconfigurableServiceMixin, service.AsyncMultiService):

    def __init__(self, master):
        service.AsyncMultiService.__init__(self)
        self.setName('wamp')
        self.master = master
        self.app = self.router_url = None
        self.serviceDeferred = defer.Deferred()
        self.service = None

    def getService(self):
        if self.service is not None:
            return defer.succeed(self.service)
        d = defer.Deferred()

        @self.serviceDeferred.addCallback
        def gotService(service):
            d.callback(service)
            return service
        return d

    @defer.inlineCallbacks
    def publish(self, topic, data, options=None):
        service = yield self.getService()
        try:
            ret = yield service.publish(topic, data, options=options)
        except TransportLost:
            log.err(failure.Failure(), "while publishing event " + topic)
            return
        defer.returnValue(ret)

    @defer.inlineCallbacks
    def call(self, topic, *args, **kwargs):
        service = yield self.getService()
        ret = yield service.call(topic, *args, **kwargs)
        defer.returnValue(ret)

    @defer.inlineCallbacks
    def register(self, callback, topic=None, options=None):
        service = yield self.getService()
        ret = yield service.register(callback, topic, options)
        defer.returnValue(ret)

    @defer.inlineCallbacks
    def subscribe(self, callback, topic=None, options=None):
        service = yield self.getService()
        ret = yield service.subscribe(callback, topic, options)
        defer.returnValue(ret)

    def reconfigServiceWithBuildbotConfig(self, new_config):
        wamp = new_config.mq.get('wamp', {})
        router_url = wamp.get('router_url', None)

        # This is not a good idea to allow people to switch the router via reconfig
        # how would we continue the current transactions ?
        # how would we tell the slaves to switch router ?
        if self.app is not None and self.router_url != router_url:
            raise ValueError("Cannot use different wamp router url when reconfiguring")
        if router_url is None:
            return
        self.router_url = router_url
        self.app = BuildbotWampService(
            url=self.router_url,
            extra=dict(master=self.master, parent=self),
            realm=wamp.get('realm'),
            make=make,
            debug=wamp.get('debug_websockets', False),
            debug_wamp=wamp.get('debug_lowlevel', False),
            debug_app=wamp.get('debug', False)
        )

        self.app.setServiceParent(self)
        return service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                    new_config)
