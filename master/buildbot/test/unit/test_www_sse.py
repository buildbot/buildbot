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
import datetime

from twisted.trial import unittest

from buildbot.test.unit import test_data_changes
from buildbot.test.util import www
from buildbot.util import datetime2epoch
from buildbot.util import json
from buildbot.www import sse


class EventResource(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = master = self.make_master(url='h:/a/b/')
        self.sse = sse.EventResource(master)

    def test_simpleapi(self):
        self.render_resource(self.sse, '/changes/*/*')
        self.readUUID(self.request)
        self.assertReceivesChangeNewMessage(self.request)
        self.assertEqual(self.request.finished, False)

    def test_listen(self):
        self.render_resource(self.sse, '/listen/changes/*/*')
        self.readUUID(self.request)
        self.assertReceivesChangeNewMessage(self.request)
        self.assertEqual(self.request.finished, False)

    def test_listen_add_then_close(self):
        self.render_resource(self.sse, '/listen')
        request = self.request
        self.request = None
        uuid = self.readUUID(request)
        self.render_resource(self.sse, '/add/' + uuid + "/changes/*/*")
        self.assertReceivesChangeNewMessage(request)
        self.assertEqual(self.request.finished, True)
        self.assertEqual(request.finished, False)
        request.finish()  # fake close connection on client side
        self.assertRaises(
            AssertionError, self.assertReceivesChangeNewMessage, request)

    def test_listen_add_then_remove(self):
        self.render_resource(self.sse, '/listen')
        request = self.request
        uuid = self.readUUID(request)
        self.render_resource(self.sse, '/add/' + uuid + "/changes/*/*")
        self.assertReceivesChangeNewMessage(request)
        self.assertEqual(request.finished, False)
        self.render_resource(self.sse, '/remove/' + uuid + "/changes/*/*")
        self.assertRaises(
            AssertionError, self.assertReceivesChangeNewMessage, request)

    def test_listen_add_nouuid(self):
        self.render_resource(self.sse, '/listen')
        request = self.request
        self.readUUID(request)
        self.render_resource(self.sse, '/add/')
        self.assertEqual(self.request.finished, True)
        self.assertEqual(self.request.responseCode, 400)
        self.assertIn("need uuid", self.request.written)

    def test_listen_add_baduuid(self):
        self.render_resource(self.sse, '/listen')
        request = self.request
        self.readUUID(request)
        self.render_resource(self.sse, '/add/foo')
        self.assertEqual(self.request.finished, True)
        self.assertEqual(self.request.responseCode, 400)
        self.assertIn("unknown uuid", self.request.written)

    def readEvent(self, request):
        kw = {}
        hasEmptyLine = False
        for line in request.written.splitlines():
            if line.find(":") > 0:
                k, v = line.split(": ", 1)
                self.assertTrue(k not in kw, k + " in " + str(kw))
                kw[k] = v
            else:
                self.assertEqual(line, "")
                hasEmptyLine = True
        request.written = ""
        self.assertTrue(hasEmptyLine)
        return kw

    def readUUID(self, request):
        kw = self.readEvent(request)
        self.assertEqual(kw["event"], "handshake")
        return kw["data"]

    def assertReceivesChangeNewMessage(self, request):
        self.master.mq.callConsumer(
            ("changes", "500", "new"), test_data_changes.Change.changeEvent)
        kw = self.readEvent(request)
        self.assertEqual(kw["event"], "event")
        msg = json.loads(kw["data"])
        self.assertEqual(msg["key"], [u'changes', u'500', u'new'])
        self.assertEqual(msg["message"], json.loads(
            json.dumps(test_data_changes.Change.changeEvent, default=self._toJson)))

    def _toJson(self, obj):
        if isinstance(obj, datetime.datetime):
            return datetime2epoch(obj)
