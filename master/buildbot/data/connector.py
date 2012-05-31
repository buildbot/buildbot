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

import inspect
from twisted.application import service
from buildbot.data import update, exceptions, base

class DataConnector(service.Service):

    def __init__(self, master):
        self.setName('data')
        self.master = master
        self.update = update.UpdateComponent(master)

        self.matcher = {}
        self._setup()

    def _setup(self):
        def _scanModule(mod):
            for sym in dir(mod):
                obj = getattr(mod, sym)
                if inspect.isclass(obj) and issubclass(obj, base.Endpoint):
                    self.matcher[obj.key] = obj(self.master)

        # scan all of the endpoint modules
        from buildbot.data import changes
        _scanModule(changes)

    def _lookup(self, path):
        try:
            return self.matcher[path]
        except KeyError:
            raise exceptions.InvalidPathError

    def get(self, path, kwargs=None, options=None):
        endpoint = self._lookup(path)
        return endpoint.get(options, kwargs)

    def startConsuming(self, callback, path, kwargs=None, options=None):
        endpoint = self._lookup(path)
        topic = endpoint.getSubscriptionTopic(options, kwargs)
        if not topic:
            raise exceptions.InvalidPathError
        # TODO: aggregate consumers of the same topics
        # TODO: double this up with get() somehow
        return self.master.mq.startConsuming(callback, topic)

    def control(self, action, args, path):
        endpoint, kwargs = self._lookup(path)
        return endpoint.control(action, args, kwargs)
