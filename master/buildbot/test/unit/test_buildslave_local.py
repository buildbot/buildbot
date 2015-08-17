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

import mock
import os

from buildbot.buildslave import local
from buildbot.test.fake import fakemaster
from twisted.internet import defer
from twisted.trial import unittest


class TestLocalBuildSlave(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, wantData=True,
                                             testcase=self)
        self.botmaster = self.master.botmaster
        self.buildslaves = self.master.buildslaves

    def createBuildslave(self, name='bot', attached=False, configured=True, **kwargs):
        slave = local.LocalBuildSlave(name, **kwargs)
        if configured:
            slave.setServiceParent(self.buildslaves)
        return slave

    @defer.inlineCallbacks
    def test_reconfigService_attrs(self):
        old = self.createBuildslave('bot',
                                    max_builds=2,
                                    notify_on_missing=['me@me.com'],
                                    missing_timeout=120,
                                    properties={'a': 'b'})
        new = self.createBuildslave('bot', configured=False,
                                    max_builds=3,
                                    notify_on_missing=['her@me.com'],
                                    missing_timeout=121,
                                    workdir=os.path.abspath('custom'),
                                    properties={'a': 'c'})

        old.updateSlave = mock.Mock(side_effect=lambda: defer.succeed(None))
        yield old.startService()
        self.assertEqual(old.remote_slave.bot.basedir, os.path.abspath('basedir/slaves/bot'))

        yield old.reconfigServiceWithSibling(new)

        self.assertEqual(old.max_builds, 3)
        self.assertEqual(old.notify_on_missing, ['her@me.com'])
        self.assertEqual(old.missing_timeout, 121)
        self.assertEqual(old.properties.getProperty('a'), 'c')
        self.assertEqual(old.registration.updates, ['bot'])
        self.assertTrue(old.updateSlave.called)
        # make sure that we can provide an abosolute path
        self.assertEqual(old.remote_slave.bot.basedir, os.path.abspath('custom'))

    @defer.inlineCallbacks
    def test_slaveinfo(self):
        sl = self.createBuildslave('bot',
                                   max_builds=2,
                                   notify_on_missing=['me@me.com'],
                                   missing_timeout=120,
                                   properties={'a': 'b'})
        yield sl.startService()
        info = yield sl.conn.remoteGetSlaveInfo()
        self.assertIn("slave_commands", info)
