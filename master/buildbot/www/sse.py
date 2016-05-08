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
import uuid

from future.utils import itervalues
from twisted.python import log
from twisted.web import resource
from twisted.web import server

from buildbot.data.exceptions import InvalidPathError
from buildbot.util import json
from buildbot.util import toJson


class Consumer(object):

    def __init__(self, request):
        self.request = request
        self.qrefs = {}

    def stopConsuming(self, key=None):
        if key is not None:
            self.qrefs[key].stopConsuming()
        else:
            for qref in itervalues(self.qrefs):
                qref.stopConsuming()
            self.qrefs = {}

    def onMessage(self, event, data):
        request = self.request
        msg = dict(key=event, message=data)
        request.write("event: " + "event" + "\n")
        request.write("data: " + json.dumps(msg, default=toJson) + "\n")
        request.write("\n")

    def registerQref(self, path, qref):
        self.qrefs[path] = qref


class EventResource(resource.Resource):
    isLeaf = True

    def __init__(self, master):
        resource.Resource.__init__(self)

        self.master = master
        self.consumers = {}

    def decodePath(self, path):
        for i, p in enumerate(path):
            if p == '*':
                path[i] = None
        return path

    def finish(self, request, code, msg):
        request.setResponseCode(code)
        request.setHeader('content-type', 'text/plain; charset=utf-8')
        request.write(msg)
        return

    def render(self, request):
        command = "listen"
        path = request.postpath
        if path and path[-1] == '':
            path = path[:-1]

        if path and path[0] in ("listen", "add", "remove"):
            command = path[0]
            path = path[1:]

        if command == "listen":
            cid = str(uuid.uuid4())
            consumer = Consumer(request)

        elif command == "add" or command == "remove":
            if path:
                cid = path[0]
                path = path[1:]
                if cid not in self.consumers:
                    return self.finish(request, 400, "unknown uuid")
                consumer = self.consumers[cid]
            else:
                return self.finish(request, 400, "need uuid")

        pathref = "/".join(path)
        path = self.decodePath(path)

        if command == "add" or (command == "listen" and path):
            options = request.args
            for k in options:
                if len(options[k]) == 1:
                    options[k] = options[k][1]

            try:
                d = self.master.mq.startConsuming(
                    consumer.onMessage,
                    tuple(path))

                @d.addCallback
                def register(qref):
                    consumer.registerQref(pathref, qref)
                d.addErrback(log.err, "while calling startConsuming")
            except NotImplementedError:
                return self.finish(request, 404, "not implemented")
            except InvalidPathError:
                return self.finish(request, 404, "not implemented")
        elif command == "remove":
            try:
                consumer.stopConsuming(pathref)
            except KeyError:
                return self.finish(request, 404, "consumer is not listening to this event")

        if command == "listen":
            self.consumers[cid] = consumer
            request.setHeader("content-type", "text/event-stream")
            request.write("")
            request.write("event: handshake\n")
            request.write("data: " + cid + "\n")
            request.write("\n")
            d = request.notifyFinish()

            @d.addBoth
            def onEndRequest(_):
                consumer.stopConsuming()
                del self.consumers[cid]

            return server.NOT_DONE_YET

        self.finish(request, 200, "ok")
        return
