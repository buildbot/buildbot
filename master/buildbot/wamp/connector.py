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

from autobahn.twisted.wamp import ApplicationRunner
from autobahn.twisted.wamp import ApplicationSession
from twisted.internet import defer

from buildbot.util import service
from buildbot.wamp import protocol


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
        config.extra['parent'].service = self
        # init and register child handlers
        p = protocol.SlaveProtoWampHandler(self.master)
        p.setServiceParent(self)

    @defer.inlineCallbacks
    def onJoin(self, details):
        for handler in [self] + self.services:
            yield self.register(handler)
            yield self.subscribe(handler)


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

    def call(self, *args, **kw):
        return self.service.call(*args, **kw)

    def reconfigServiceWithBuildbotConfig(self, new_config):
        wamp = new_config.protocols.get('wamp', {})
        router_url = wamp.get('router_url', None)

        # This is not a good idea to allow people to switch the router via reconfig
        # how would we continue the current transactions ?
        # how would we tell the slaves to switch router ?
        if self.app is not None and self.router_url != router_url:
            raise ValueError("Cannot use different wamp router url when reconfiguring")
        if router_url is None:
            return
        self.router_url = router_url
        self.app = ApplicationRunner(
            url=self.router_url,
            extra=dict(master=self.master, parent=self),
            realm=wamp.get('realm'),
            debug=wamp.get('debug_websockets', False),
            debug_wamp=wamp.get('debug_lowlevel', False),
            debug_app=wamp.get('debug', False)
        )

        self.app.run(make, start_reactor=False)
        return service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                    new_config)
