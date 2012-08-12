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

import os
from buildbot.www import ui, service
from buildbot.test.util import www
from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.python import failure

class Test(www.WwwTestMixin, unittest.TestCase):
    def test_render(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = ui.UIResource(master)

        d = self.render_resource(rsrc, [''])
        @d.addCallback
        def check(rv):
            self.assertIn('base_url:"h:/a/b/"', rv)
        return d

try:
    from buildbot.test.util.txghost import Ghost
    has_ghost= Ghost != None
except ImportError:
    # if $REQUIRE_GHOST is set, then fail if it's not found
    if os.environ.get('REQUIRE_GHOST'):
        raise
    has_ghost=False

class TestGhostPy(www.WwwTestMixin, unittest.TestCase):
    if not has_ghost:
        skip = "Need Ghost.py to run most of www_ui tests"

    @defer.inlineCallbacks
    def setUp(self):
        # hack to prevent twisted.web.http to setup a 1 sec callback at init
        import twisted
        #twisted.internet.base.DelayedCall.debug = True
        twisted.web.http._logDateTimeUsers = 1
        # lets resolve the tested port unicity later...
        port = 8010
        self.url = 'http://localhost:'+str(port)+"/"
        self.master = self.make_master(url=self.url, port=port)
        self.svc = service.WWWService(self.master)
        yield self.svc.startService()
        yield self.svc.reconfigService(self.master.config)
        self.ghost = Ghost()

    @defer.inlineCallbacks
    def tearDown(self):
        from  twisted.internet.tcp import Server
        del self.ghost
        yield self.svc.stopService()
        # webkit has the bad habbit on not closing the persistent
        # connections, so we need to hack them away to make trial happy
        for reader in reactor.getReaders():
            if isinstance(reader, Server):
                f = failure.Failure(Exception("test end"))
                reader.connectionLost(f)

    @defer.inlineCallbacks
    def test_home(self):
        yield self.ghost.open(self.url)
        yield self.ghost.wait_for_selector("ul.breadcrumb")
        base_url, resources = self.ghost.evaluate("bb_router.base_url")
        assert(base_url== self.url)
