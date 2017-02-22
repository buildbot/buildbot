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

from buildbot.mq import base
from buildbot.test.util import validation
from buildbot.util import service
from buildbot.util import tuplematch


class FakeMQConnector(service.AsyncMultiService, base.MQBase):

    # a fake connector that doesn't actually bridge messages from production to
    # consumption, and thus doesn't do any topic handling or persistence

    # note that this *does* verify all messages sent and received, unless this
    # is set to false:
    verifyMessages = True

    def __init__(self, testcase):
        service.AsyncMultiService.__init__(self)
        self.testcase = testcase
        self.setup_called = False
        self.productions = []
        self.qrefs = []

    def setup(self):
        self.setup_called = True
        return defer.succeed(None)

    def produce(self, routingKey, data):
        self.testcase.assertIsInstance(routingKey, tuple)

# XXX this is incompatible with the new scheme of sending multiple messages,
# since the message type is no longer encoded by the first element of the
# routing key
#        if self.verifyMessages:
#            validation.verifyMessage(self.testcase, routingKey, data)

        if any(not isinstance(k, str) for k in routingKey):
            raise AssertionError("%s is not all str" % (routingKey,))
        self.productions.append((routingKey, data))
        # note - no consumers are called: IT'S A FAKE

    def callConsumer(self, routingKey, msg):
        if self.verifyMessages:
            validation.verifyMessage(self.testcase, routingKey, msg)
        matched = False
        for q in self.qrefs:
            if tuplematch.matchTuple(routingKey, q.filter):
                matched = True
                q.callback(routingKey, msg)
        if not matched:
            raise AssertionError("no consumer found")

    def startConsuming(self, callback, filter, persistent_name=None):
        if any(not isinstance(k, str) and
               k is not None for k in filter):
            raise AssertionError("%s is not a filter" % (filter,))
        qref = FakeQueueRef()
        qref.qrefs = self.qrefs
        qref.callback = callback
        qref.filter = filter
        qref.persistent_name = persistent_name
        self.qrefs.append(qref)
        return defer.succeed(qref)

    def clearProductions(self):
        "Clear out the cached productions"
        self.productions = []

    def assertProductions(self, exp, orderMatters=True):
        """Assert that the given messages have been produced, then flush the
        list of produced messages.

        If C{orderMatters} is false, then the messages are sorted first; use
        this in cases where the messages must all be produced, but the order is
        not specified.
        """
        if orderMatters:
            self.testcase.assertEqual(self.productions, exp)
        else:
            self.testcase.assertEqual(sorted(self.productions), sorted(exp))
        self.productions = []


class FakeQueueRef(object):

    def stopConsuming(self):
        if self in self.qrefs:
            self.qrefs.remove(self)
