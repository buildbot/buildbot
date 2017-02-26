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

from twisted.internet import defer

from buildbot.test.e2e.base import DaemonMixin
from buildbot.test.e2e.base import E2ETestBase
from buildbot.test.e2e.base import buildbot_worker_executable
from buildbot.test.e2e.base import buildslave_executable
from buildbot.test.e2e.base import wait_for_completion
from buildbot.test.util.decorators import skipIf
from buildbot.test.util.decorators import skipUnlessPlatformIs


FILE_UPLOAD_TEST_CONFIG = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['buildbotNetUsageData'] = None

c['workers'] = [worker.Worker('example-worker', 'pass')]
c['protocols'] = {'pb': {'port': 9989}}
c['schedulers'] = [
    schedulers.ForceScheduler(
        name='force',
        builderNames=['runtests'])
]

factory = util.BuildFactory()
factory.addStep(
    steps.StringDownload("filecontent", workerdest="dir/file1.txt"))
factory.addStep(
    steps.StringDownload("filecontent2", workerdest="dir/file2.txt"))
factory.addStep(
    steps.FileUpload(workersrc="dir/file2.txt", masterdest="master.txt"))
factory.addStep(
    steps.FileDownload(mastersrc="master.txt", workerdest="dir/file3.txt"))
factory.addStep(steps.DirectoryUpload(workersrc="dir", masterdest="dir"))

c['builders'] = [
    util.BuilderConfig(name='runtests', workernames=['example-worker'],
        factory=factory),
]

c['buildbotURL'] = 'http://localhost:8010/'
c['www'] = dict(port=8010, plugins={})
c['db'] = {
    'db_url' : 'sqlite:///state.sqlite',
}
"""


def _read_dir_contents(dirname):
    contents = {}
    for root, _, files in os.walk(dirname):
        for name in files:
            filename = os.path.join(root, name)
            with open(filename) as f:
                contents[filename] = f.read()
    return contents


class FileTransferTestMixin:

    @defer.inlineCallbacks
    def run_check(self, master_dir):
        # Get builder ID.
        # TODO: maybe add endpoint to get builder by name?
        builders = yield self._get('builders')
        self.assertEqual(len(builders['builders']), 1)
        builder_id = builders['builders'][0]['builderid']

        # Start force build.
        # TODO: return result is not documented in RAML.
        buildset_id, buildrequests_ids = yield self._call_rpc(
            'forceschedulers/force', 'force', builderid=builder_id)

        @defer.inlineCallbacks
        def is_completed():
            # Query buildset completion status.
            buildsets = yield self._get('buildsets/{0}'.format(buildset_id))
            defer.returnValue(buildsets['buildsets'][0]['complete'])

        yield wait_for_completion(is_completed)

        # TODO: Looks like there is no easy way to get build identifier that
        # corresponds to buildrequest/buildset.
        buildnumber = 1

        # Get completed build info.
        builds = yield self._get(
            'builders/{builderid}/builds/{buildnumber}'.format(
                builderid=builder_id, buildnumber=buildnumber))

        self.assertEqual(builds['builds'][0]['state_string'], 'finished')

        master_contents = _read_dir_contents(os.path.join(master_dir, "dir"))
        self.assertEqual(
            master_contents,
            {os.path.join(master_dir, 'dir', 'file1.txt'): 'filecontent',
             os.path.join(master_dir, 'dir', 'file2.txt'): 'filecontent2',
             os.path.join(master_dir, 'dir', 'file3.txt'): 'filecontent2'})


class FileTransferOnWorkerNoDaemonTest(E2ETestBase, FileTransferTestMixin):

    @defer.inlineCallbacks
    def check_file_transfer_on_worker(
            self,
            master_executable=None,
            worker_executable=None):
        """Run file transfer between master/worker."""

        master_dir = 'master-dir'

        yield self.setupEnvironment({
            'masters': [
                (master_dir, FILE_UPLOAD_TEST_CONFIG, master_executable),
            ],
            'workers': [
                ('worker-dir', 'example-worker', 'pass', worker_executable),
            ],
        })

        yield self.run_check(master_dir)

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    def test_file_transfer_on_worker(self):
        yield self.check_file_transfer_on_worker()


@skipUnlessPlatformIs('posix')
class FileTransferOnWorkerDaemonTest(
        FileTransferOnWorkerNoDaemonTest, DaemonMixin):
    pass


class FileTransferOnSlaveNoDaemonTest(E2ETestBase, FileTransferTestMixin):

    @defer.inlineCallbacks
    def check_file_transfer_on_slave(
            self,
            master_executable=None,
            slave_executable=None):
        """Run file transfer between master/buildslave."""

        master_dir = 'master-dir'

        yield self.setupEnvironment({
            'masters': [
                (master_dir, FILE_UPLOAD_TEST_CONFIG, master_executable),
            ],
            'slaves': [
                ('worker-dir', 'example-worker', 'pass', slave_executable),
            ],
        })

        yield self.run_check(master_dir)

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_file_transfer_on_slave(self):
        yield self.check_file_transfer_on_slave()


@skipUnlessPlatformIs('posix')
class FileTransferOnSlaveDaemonTest(
        FileTransferOnSlaveNoDaemonTest, DaemonMixin):
    pass
