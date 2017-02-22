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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import itervalues

import json
import uuid

from twisted.python import log
from twisted.web import resource
from twisted.web import server

from buildbot.data.exceptions import InvalidPathError
from buildbot.util import bytes2NativeString
from buildbot.util import toJson
from buildbot.util import unicode2bytes


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
        key = [bytes2NativeString(e) for e in event]
        msg = dict(key=key, message=data)
        request.write(b"event: " + b"event" + b"\n")
        request.write(
            b"data: " + unicode2bytes(json.dumps(msg, default=toJson)) + b"\n")
        request.write(b"\n")

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
            if p == b'*':
                path[i] = None
        return path

    def finish(self, request, code, msg):
        request.setResponseCode(code)
        request.setHeader('content-type', 'text/plain; charset=utf-8')
        request.write(msg)
        return

    def render(self, request):
        command = b"listen"
        path = request.postpath
        if path and path[-1] == b'':
            path = path[:-1]

        if path and path[0] in (b"listen", b"add", b"remove"):
            command = path[0]
            path = path[1:]

        if command == b"listen":
            cid = unicode2bytes(str(uuid.uuid4()))
            consumer = Consumer(request)

        elif command == b"add" or command == b"remove":
            if path:
                cid = path[0]
                path = path[1:]
                if cid not in self.consumers:
                    return self.finish(request, 400, b"unknown uuid")
                consumer = self.consumers[cid]
            else:
                return self.finish(request, 400, b"need uuid")

        pathref = b"/".join(path)
        path = self.decodePath(path)

        if command == b"add" or (command == b"listen" and path):
            options = request.args
            for k in options:
                if len(options[k]) == 1:
                    options[k] = options[k][1]

            try:
                d = self.master.mq.startConsuming(
                    consumer.onMessage,
                    tuple([bytes2NativeString(p) for p in path]))

                @d.addCallback
                def register(qref):
                    consumer.registerQref(pathref, qref)
                d.addErrback(log.err, "while calling startConsuming")
            except NotImplementedError:
                return self.finish(request, 404, b"not implemented")
            except InvalidPathError:
                return self.finish(request, 404, b"not implemented")
        elif command == b"remove":
            try:
                consumer.stopConsuming(pathref)
            except KeyError:
                return self.finish(request, 404, b"consumer is not listening to this event")

        if command == b"listen":
            self.consumers[cid] = consumer
            request.setHeader(b"content-type", b"text/event-stream")
            request.write(b"")
            request.write(b"event: handshake\n")
            request.write(b"data: " + cid + b"\n")
            request.write(b"\n")
            d = request.notifyFinish()

            @d.addBoth
            def onEndRequest(_):
                consumer.stopConsuming()
                del self.consumers[cid]

            return server.NOT_DONE_YET

        self.finish(request, 200, b"ok")
        return
