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

from buildbot.www.plugin import Application
from twisted.web.wsgi import WSGIResource
from twisted.internet import reactor
from buildbot.util import unicode2bytes
from twisted.internet.threads import blockingCallFromThread


class WSGIDashboardsApplication(Application):

    def setConfiguration(self, config):
        for dashboard in config:
            dashboard['app'].buildbot_api = self
            resource = WSGIResource(reactor, reactor.getThreadPool(), dashboard['app'])
            self.resource.putChild(unicode2bytes(dashboard['name']), resource)

    def dataGet(self, path, **kwargs):
        if not isinstance(path, tuple):
            path = tuple(path.strip("/").split("/"))
        return blockingCallFromThread(reactor, self.master.data.get, path, **kwargs)


# create the interface for the setuptools entry point
ep = WSGIDashboardsApplication(__name__, "Buildbot WSGI Dashboard Glue")
