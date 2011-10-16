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

from twisted.internet import defer

class FakeMQConnector(object):

    # a fake connector that doesn't actually bridge messages from production to
    # consumption, and thus doesn't do any topic handling or persistence

    def __init__(self, master):
        self.master = master
        self.setup_called = False
        self.productions = []
        self.qrefs = []

    def setup(self):
        self.setup_called = True
        return defer.succeed(None)

    def produce(self, routing_key, data):
        self.productions.append((routing_key, data))

    def call_consumer(self, topic, key, msg):
        for q in self.qrefs:
            if topic in q.topics:
                return q.callback(key, msg)
        else:
            assert 0, "no consumer found"

    def startConsuming(self, callback, *topics, **kwargs):
        qref = FakeQueueRef()
        qref.qrefs = self.qrefs
        qref.callback = callback
        qref.topics = topics
        qref.kwargs = kwargs
        self.qrefs.append(qref)
        return qref

class FakeQueueRef(object):

    def stopConsuming(self):
        if self in self.qrefs:
            self.qrefs.remove(self)
