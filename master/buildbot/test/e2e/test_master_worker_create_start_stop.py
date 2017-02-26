from __future__ import absolute_import
from __future__ import print_function

import os
import re
import textwrap

from twisted.internet import defer

from buildbot.test.e2e.base import E2ETestBase
from buildbot.test.e2e.base import buildbot_worker_executable
from buildbot.test.e2e.base import buildslave_executable
from buildbot.test.util.decorators import skipIf
from buildbot.util.indent import indent


class TestMasterWorkerSetup(E2ETestBase):

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    def test_master_worker_setup(self):
        """Create master and worker (with default pyflakes configuration),
        start them, stop them.
        """

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Create master.cfg based on sample file.
        sample_config = os.path.join(master_dir, 'master.cfg.sample')
        with open(sample_config, 'rt') as f:
            master_cfg = f.read()

        # Disable www plugins (they are not installed on Travis).
        master_cfg = re.sub(r"plugins=dict\([^)]+\)", "plugins={}", master_cfg)
        # Disable usage reporting.
        master_cfg += """\nc['buildbotNetUsageData'] = None\n"""

        self._write_master_config(master_dir, master_cfg)

        # Create worker.
        worker_dir = 'worker-dir'
        yield self._buildbot_worker_create_worker(
            worker_dir, 'example-worker', 'pass')

        # Start.
        yield self._buildbot_start(master_dir)
        yield self._buildbot_worker_start(worker_dir)

        # Stop.
        yield self._buildbot_worker_stop(worker_dir)
        yield self._buildbot_stop(master_dir)

        # Check master logs.
        with open(os.path.join(master_dir, "twistd.log"), 'rt') as f:
            log = f.read()

        # Check that worker info was received without warnings.
        worker_connection_re = textwrap.dedent(
            r"""
            [^\n]+ worker 'example-worker' attaching from [^\n]+
            [^\n]+ Got workerinfo from 'example-worker'
            """)

        self.assertTrue(
            re.search(worker_connection_re, log, re.MULTILINE),
            msg="Log doesn't match:\n{0}\nLog:\n{1}".format(
                indent(worker_connection_re, "    "),
                indent(log, "    ")))

    @defer.inlineCallbacks
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_master_slave_setup(self):
        """Create master and slave (with default pyflakes configuration),
        start them, stop them.
        """

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Create master.cfg based on sample file.
        sample_config = os.path.join(master_dir, 'master.cfg.sample')
        with open(sample_config, 'rt') as f:
            master_cfg = f.read()

        # Disable www plugins (they are not installed on Travis).
        master_cfg = re.sub(r"plugins=dict\([^)]+\)", "plugins={}", master_cfg)
        # Disable usage reporting.
        master_cfg += """\nc['buildbotNetUsageData'] = None\n"""

        self._write_master_config(master_dir, master_cfg)

        # Create slave.
        slave_dir = 'slave-dir'
        yield self._buildslave_create_slave(
            slave_dir, 'example-worker', 'pass')

        # Start.
        yield self._buildbot_start(master_dir)
        yield self._buildslave_start(slave_dir)

        # Stop.
        yield self._buildslave_stop(slave_dir)
        yield self._buildbot_stop(master_dir)

        # Check master logs.
        with open(os.path.join(master_dir, "twistd.log"), 'rt') as f:
            log = f.read()

        # Check that slave info was received with message about fallback from
        # buildbot-worker methods.
        worker_connection_re = textwrap.dedent(
            r"""
            [^\n]+ worker 'example-worker' attaching from [^\n]+
            [^\n]+ Worker.getWorkerInfo is unavailable - falling back [^\n]+
            [^\n]+ Got workerinfo from 'example-worker'
            """)

        self.assertTrue(
            re.search(worker_connection_re, log, re.MULTILINE),
            msg="Log doesn't match:\n{0}\nLog:\n{1}".format(
                indent(worker_connection_re, "    "),
                indent(log, "    ")))
