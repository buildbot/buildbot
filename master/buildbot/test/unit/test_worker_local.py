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

import os

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import fakemaster
from buildbot.worker import local


class TestLocalWorker(unittest.TestCase):

    try:
        from buildbot_worker.bot import LocalWorker as _  # noqa
    except ImportError:
        skip = "buildbot-worker package is not installed"

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, wantData=True,
                                             testcase=self)
        self.botmaster = self.master.botmaster
        self.workers = self.master.workers

    def createWorker(self, name='bot', attached=False, configured=True, **kwargs):
        worker = local.LocalWorker(name, **kwargs)
        if configured:
            worker.setServiceParent(self.workers)
        return worker

    @defer.inlineCallbacks
    def test_reconfigService_attrs(self):
        old = self.createWorker('bot',
                                max_builds=2,
                                notify_on_missing=['me@me.com'],
                                missing_timeout=120,
                                properties={'a': 'b'})
        new = self.createWorker('bot', configured=False,
                                max_builds=3,
                                notify_on_missing=['her@me.com'],
                                missing_timeout=121,
                                workdir=os.path.abspath('custom'),
                                properties={'a': 'c'})

        old.updateWorker = mock.Mock(side_effect=lambda: defer.succeed(None))
        yield old.startService()
        self.assertEqual(
            old.remote_worker.bot.basedir, os.path.abspath('basedir/workers/bot'))

        yield old.reconfigServiceWithSibling(new)

        self.assertEqual(old.max_builds, 3)
        self.assertEqual(old.notify_on_missing, ['her@me.com'])
        self.assertEqual(old.missing_timeout, 121)
        self.assertEqual(old.properties.getProperty('a'), 'c')
        self.assertEqual(old.registration.updates, ['bot'])
        self.assertTrue(old.updateWorker.called)
        # make sure that we can provide an absolute path
        self.assertEqual(
            old.remote_worker.bot.basedir, os.path.abspath('custom'))
        yield old.stopService()

    @defer.inlineCallbacks
    def test_workerinfo(self):
        wrk = self.createWorker('bot',
                                max_builds=2,
                                notify_on_missing=['me@me.com'],
                                missing_timeout=120,
                                properties={'a': 'b'})
        yield wrk.startService()
        info = yield wrk.conn.remoteGetWorkerInfo()
        self.assertIn("worker_commands", info)
        yield wrk.stopService()
