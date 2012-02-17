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

from buildbot.status.web import base
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest

class ActionResource(unittest.TestCase):

    def test_ActionResource_success(self):

        class MyActionResource(base.ActionResource):
            def performAction(self, request):
                self.got_request = request
                return defer.succeed('http://buildbot.net')

        rsrc = MyActionResource()
        request = FakeRequest()
        rsrc.render(request)
        d = request.deferred

        def check(_):
            self.assertIdentical(rsrc.got_request, request)
            self.assertTrue(request.finished)
            self.assertIn('buildbot.net', request.written)
            self.assertEqual(request.redirected_to, 'http://buildbot.net')
        d.addCallback(check)
        return d

    def test_ActionResource_exception(self):

        class MyActionResource(base.ActionResource):
            def performAction(self, request):
                return defer.fail(RuntimeError('sacrebleu'))

        rsrc = MyActionResource()
        request = FakeRequest()
        rsrc.render(request)
        d = request.deferred

        def check(f):
            f.trap(RuntimeError)
            # pass - all good!
        d.addErrback(check)
        return d

