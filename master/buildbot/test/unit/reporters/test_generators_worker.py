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

from parameterized import parameterized

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.reporters.generators.worker import WorkerMissingGenerator
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin


class TestWorkerMissingGenerator(ConfigErrorsMixin, TestReactorMixin,
                                 unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    def _get_worker_dict(self, worker_name):
        return {
            'name': worker_name,
            'notify': ["workeradmin@example.org"],
            'workerinfo': {"admin": "myadmin"},
            'last_connection': "yesterday"
        }

    @parameterized.expand([
        (['myworker'],),
        ('all',),
    ])
    @defer.inlineCallbacks
    def test_report_matched_worker(self, worker_filter):
        g = WorkerMissingGenerator(workers=worker_filter)

        report = yield g.generate(self.master, None, 'worker.98.complete',
                                  self._get_worker_dict('myworker'))

        self.assertEqual(report['users'], ['workeradmin@example.org'])
        self.assertIn(b"worker named myworker went away", report['body'])

    @defer.inlineCallbacks
    def test_report_not_matched_worker(self):
        g = WorkerMissingGenerator(workers=['other'])

        report = yield g.generate(self.master, None, 'worker.98.complete',
                                  self._get_worker_dict('myworker'))

        self.assertIsNone(report)

    def test_unsupported_workers(self):
        g = WorkerMissingGenerator(workers='string worker')
        with self.assertRaisesConfigError("workers must be 'all', or list of worker names"):
            g.check()
