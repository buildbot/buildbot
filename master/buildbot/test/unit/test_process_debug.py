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
from twisted.trial import unittest
from twisted.internet import defer
from twisted.application import service
from buildbot.process import debug
from buildbot import config

class FakeManhole(service.Service):
    pass

class TestDebugServices(unittest.TestCase):

    def setUp(self):
        self.master = mock.Mock(name='master')
        self.config = config.MasterConfig()

    @defer.inlineCallbacks
    def test_reconfigService_debug(self):
        # mock out PBManager
        self.master.pbmanager = pbmanager = mock.Mock()
        registration = mock.Mock(name='registration')
        registration.unregister = mock.Mock(name='unregister',
                    side_effect=lambda : defer.succeed(None))
        pbmanager.register.return_value = registration

        ds = debug.DebugServices(self.master)
        ds.startService()

        # start off with no debug password
        self.config.slavePortnum = '9824'
        self.config.debugPassword = None
        yield ds.reconfigService(self.config)

        self.assertFalse(pbmanager.register.called)

        # set the password, and see it register
        self.config.debugPassword = 'seeeekrit'
        yield ds.reconfigService(self.config)

        self.assertTrue(pbmanager.register.called)
        self.assertEqual(pbmanager.register.call_args[0][:3],
                ('9824', 'debug', 'seeeekrit'))
        factory = pbmanager.register.call_args[0][3]
        self.assertIsInstance(factory(mock.Mock(), mock.Mock()),
                debug.DebugPerspective)

        # change the password, and see it re-register
        self.config.debugPassword = 'lies'
        pbmanager.register.reset_mock()
        yield ds.reconfigService(self.config)

        self.assertTrue(registration.unregister.called)
        self.assertTrue(pbmanager.register.called)
        self.assertEqual(pbmanager.register.call_args[0][:3],
                ('9824', 'debug', 'lies'))

        # remove the password, and see it unregister
        self.config.debugPassword = None
        pbmanager.register.reset_mock()
        registration.unregister.reset_mock()
        yield ds.reconfigService(self.config)

        self.assertTrue(registration.unregister.called)
        self.assertFalse(pbmanager.register.called)

        # re-register to test stopService
        self.config.debugPassword = 'confusion'
        pbmanager.register.reset_mock()
        yield ds.reconfigService(self.config)

        # stop the service, and see that it unregisters
        pbmanager.register.reset_mock()
        registration.unregister.reset_mock()
        yield ds.stopService()

        self.assertTrue(registration.unregister.called)

    @defer.inlineCallbacks
    def test_reconfigService_manhole(self):
        master = mock.Mock(name='master')
        ds = debug.DebugServices(master)
        ds.startService()

        # start off with no manhole
        yield ds.reconfigService(self.config)

        # set a manhole, fire it up
        self.config.manhole = manhole = FakeManhole()
        yield ds.reconfigService(self.config)

        self.assertTrue(manhole.running)
        self.assertIdentical(manhole.master, master)

        # unset it, see it stop
        self.config.manhole = None
        yield ds.reconfigService(self.config)

        self.assertFalse(manhole.running)
        self.assertIdentical(manhole.master, None)

        # re-start to test stopService
        self.config.manhole = manhole
        yield ds.reconfigService(self.config)

        # stop the service, and see that it unregisters
        yield ds.stopService()

        self.assertFalse(manhole.running)
        self.assertIdentical(manhole.master, None)


class TestDebugPerspective(unittest.TestCase):

    def setUp(self):
        self.master = mock.Mock()
        self.persp = debug.DebugPerspective(self.master)

    def test_attached(self):
        self.assertIdentical(self.persp.attached(mock.Mock()), self.persp)

    def test_detached(self):
        self.persp.detached(mock.Mock()) # just shouldn't crash

    def test_perspective_reload(self):
        d = defer.maybeDeferred(lambda : self.persp.perspective_reload())
        def check(_):
            self.master.reconfig.assert_called_with()
        d.addCallback(check)
        return d

    # remaining methods require IControl adapters or other weird stuff.. TODO
