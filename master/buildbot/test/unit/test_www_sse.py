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

import datetime
import json

from twisted.trial import unittest

from buildbot.test.unit import test_data_changes
from buildbot.test.util import www
from buildbot.util import bytes2NativeString
from buildbot.util import datetime2epoch
from buildbot.util import unicode2bytes
from buildbot.www import sse


class EventResource(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = master = self.make_master(url=b'h:/a/b/')
        self.sse = sse.EventResource(master)

    def test_simpleapi(self):
        self.render_resource(self.sse, b'/changes/*/*')
        self.readUUID(self.request)
        self.assertReceivesChangeNewMessage(self.request)
        self.assertEqual(self.request.finished, False)

    def test_listen(self):
        self.render_resource(self.sse, b'/listen/changes/*/*')
        self.readUUID(self.request)
        self.assertReceivesChangeNewMessage(self.request)
        self.assertEqual(self.request.finished, False)

    def test_listen_add_then_close(self):
        self.render_resource(self.sse, b'/listen')
        request = self.request
        self.request = None
        uuid = self.readUUID(request)
        self.render_resource(self.sse, b'/add/' +
                             unicode2bytes(uuid) + b"/changes/*/*")
        self.assertReceivesChangeNewMessage(request)
        self.assertEqual(self.request.finished, True)
        self.assertEqual(request.finished, False)
        request.finish()  # fake close connection on client side
        self.assertRaises(
            AssertionError, self.assertReceivesChangeNewMessage, request)

    def test_listen_add_then_remove(self):
        self.render_resource(self.sse, b'/listen')
        request = self.request
        uuid = self.readUUID(request)
        self.render_resource(self.sse, b'/add/' +
                             unicode2bytes(uuid) + b"/changes/*/*")
        self.assertReceivesChangeNewMessage(request)
        self.assertEqual(request.finished, False)
        self.render_resource(self.sse, b'/remove/' +
                             unicode2bytes(uuid) + b"/changes/*/*")
        self.assertRaises(
            AssertionError, self.assertReceivesChangeNewMessage, request)

    def test_listen_add_nouuid(self):
        self.render_resource(self.sse, b'/listen')
        request = self.request
        self.readUUID(request)
        self.render_resource(self.sse, b'/add/')
        self.assertEqual(self.request.finished, True)
        self.assertEqual(self.request.responseCode, 400)
        self.assertIn(b"need uuid", self.request.written)

    def test_listen_add_baduuid(self):
        self.render_resource(self.sse, b'/listen')
        request = self.request
        self.readUUID(request)
        self.render_resource(self.sse, b'/add/foo')
        self.assertEqual(self.request.finished, True)
        self.assertEqual(self.request.responseCode, 400)
        self.assertIn(b"unknown uuid", self.request.written)

    def readEvent(self, request):
        kw = {}
        hasEmptyLine = False
        for line in request.written.splitlines():
            if line.find(b":") > 0:
                k, v = line.split(b": ", 1)
                self.assertTrue(k not in kw, k + b" in " +
                                unicode2bytes(str(kw)))
                kw[k] = v
            else:
                self.assertEqual(line, b"")
                hasEmptyLine = True
        request.written = b""
        self.assertTrue(hasEmptyLine)
        return kw

    def readUUID(self, request):
        kw = self.readEvent(request)
        self.assertEqual(kw[b"event"], b"handshake")
        return kw[b"data"]

    def assertReceivesChangeNewMessage(self, request):
        self.master.mq.callConsumer(
            ("changes", "500", "new"), test_data_changes.Change.changeEvent)
        kw = self.readEvent(request)
        self.assertEqual(kw[b"event"], b"event")
        msg = json.loads(bytes2NativeString(kw[b"data"]))
        self.assertEqual(msg["key"], [u'changes', u'500', u'new'])
        self.assertEqual(msg["message"], json.loads(
            json.dumps(test_data_changes.Change.changeEvent, default=self._toJson)))

    def _toJson(self, obj):
        if isinstance(obj, datetime.datetime):
            return datetime2epoch(obj)
