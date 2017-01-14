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

from twisted.internet import defer
from twisted.python import failure
from twisted.python import log

from buildbot.util import service


class MQBase(service.AsyncService):
    name = 'mq-implementation'

    @defer.inlineCallbacks
    def waitUntilEvent(self, filter, check_callback):
        d = defer.Deferred()
        buildCompleteConsumer = yield self.startConsuming(
            lambda key, value: d.callback((key, value)),
            filter)
        check = yield check_callback()
        # we only wait if the check callback return true
        if not check:
            res = yield d
        yield buildCompleteConsumer.stopConsuming
        defer.returnValue(res)


class QueueRef(object):

    __slots__ = ['callback']

    def __init__(self, callback):
        self.callback = callback

    def invoke(self, routing_key, data):
        if not self.callback:
            return

        try:
            x = self.callback(routing_key, data)
        except Exception:
            log.err(failure.Failure(), 'while invoking %r' % (self.callback,))
            return
        if isinstance(x, defer.Deferred):
            x.addErrback(log.err, 'while invoking %r' % (self.callback,))

    def stopConsuming(self):
        # subclasses should set self.callback to None in this method
        raise NotImplementedError
