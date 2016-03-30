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
import re

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

import buildbot.worker

from buildbot import config
from buildbot.master import BuildMaster
from buildbot.test.util import dirs
from buildbot.test.util import www
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


# Template for master configuration just before worker renaming.
sample_0_9_0b5 = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['slaves'] = [buildslave.BuildSlave("example-slave", "pass")]

c['protocols'] = {'pb': {'port': 'tcp:0'}}

c['change_source'] = []
c['change_source'].append(changes.GitPoller(
        'git://github.com/buildbot/pyflakes.git',
        workdir='gitpoller-workdir', branch='master',
        pollinterval=300))

c['schedulers'] = []
c['schedulers'].append(schedulers.SingleBranchScheduler(
                            name="all",
                            change_filter=util.ChangeFilter(branch='master'),
                            treeStableTimer=None,
                            builderNames=["runtests"]))
c['schedulers'].append(schedulers.ForceScheduler(
                            name="force",
                            builderNames=["runtests"]))

factory = util.BuildFactory()
factory.addStep(steps.Git(repourl='git://github.com/buildbot/pyflakes.git', mode='incremental'))
factory.addStep(steps.ShellCommand(command=["trial", "pyflakes"]))

c['builders'] = []
c['builders'].append(
    util.BuilderConfig(name="runtests",
      slavenames=["example-slave"],
      factory=factory))

c['status'] = []

c['title'] = "Pyflakes"
c['titleURL'] = "https://launchpad.net/pyflakes"

c['buildbotURL'] = "http://localhost:8010/"

c['db'] = {
    'db_url' : "sqlite:///state.sqlite",
}
"""

# Template for master configuration after renaming.
sample_0_9_0b5_api_renamed = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['workers'] = [worker.Worker("example-worker", "pass")]

c['protocols'] = {'pb': {'port': 'tcp:0'}}

c['change_source'] = []
c['change_source'].append(changes.GitPoller(
        'git://github.com/buildbot/pyflakes.git',
        workdir='gitpoller-workdir', branch='master',
        pollinterval=300))

c['schedulers'] = []
c['schedulers'].append(schedulers.SingleBranchScheduler(
                            name="all",
                            change_filter=util.ChangeFilter(branch='master'),
                            treeStableTimer=None,
                            builderNames=["runtests"]))
c['schedulers'].append(schedulers.ForceScheduler(
                            name="force",
                            builderNames=["runtests"]))

factory = util.BuildFactory()
factory.addStep(steps.Git(repourl='git://github.com/buildbot/pyflakes.git', mode='incremental'))
factory.addStep(steps.ShellCommand(command=["trial", "pyflakes"]))

c['builders'] = []
c['builders'].append(
    util.BuilderConfig(name="runtests",
      workernames=["example-worker"],
      factory=factory))

c['status'] = []

c['title'] = "Pyflakes"
c['titleURL'] = "https://launchpad.net/pyflakes"

c['buildbotURL'] = "http://localhost:8010/"

c['db'] = {
    'db_url' : "sqlite:///state.sqlite",
}
"""


class RunMaster(dirs.DirsMixin, www.RequiresWwwMixin, unittest.TestCase):

    """Test that master can actually run with configuration after renaming."""

    def setUp(self):
        self.basedir = os.path.abspath('basdir')
        self.setUpDirs(self.basedir)
        self.configfile = os.path.join(self.basedir, 'master.cfg')

    def tearDown(self):
        return self.tearDownDirs()

    @defer.inlineCallbacks
    def _run_master(self, loaded_config):
        # create the master
        m = BuildMaster(self.basedir, self.configfile)

        # update the DB
        yield m.db.setup(check_version=False)
        yield m.db.model.upgrade()

        # stub out m.db.setup since it was already called above
        m.db.setup = lambda: None

        # mock reactor.stop (which trial *really* doesn't
        # like test code to call!)
        mock_reactor = mock.Mock(spec=reactor)
        mock_reactor.callWhenRunning = reactor.callWhenRunning

        # mock configuration loading
        @classmethod
        def loadConfig(cls, basedir, filename):
            return loaded_config

        with mock.patch('buildbot.config.MasterConfig.loadConfig', loadConfig):
            # start the service
            yield m.startService(_reactor=mock_reactor)
        self.failIf(mock_reactor.stop.called,
                    "startService tried to stop the reactor; check logs")

        # hang out for a fraction of a second, to let startup processes run
        d = defer.Deferred()
        reactor.callLater(0.01, d.callback, None)
        yield d

        # stop the service
        yield m.stopService()

        # and shutdown the db threadpool, as is normally done at reactor stop
        m.db.pool.shutdown()

        # (trial will verify all reactor-based timers have been cleared, etc.)

    def _write_config(self, config_str):
        with open(self.configfile, "w") as f:
            f.write(config_str)

    def test_config_0_9_0b5(self):
        # Load configuration and start master.
        # TODO: check for expected warnings.
        self._write_config(sample_0_9_0b5)

        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"'buildbot\.plugins\.buildslave' plugins namespace is deprecated",
                    r"'slavenames' keyword argument is deprecated",
                    r"c\['slaves'\] key is deprecated"]):
            loaded_config = config.MasterConfig.loadConfig(
                self.basedir, self.configfile)

        return self._run_master(loaded_config)

    def test_config_0_9_0b5_api_renamed(self):
        # Load configuration and start master.
        # TODO: check for expected warnings.

        self._write_config(sample_0_9_0b5_api_renamed)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            loaded_config = config.MasterConfig.loadConfig(
                self.basedir, self.configfile)

        return self._run_master(loaded_config)


class PluginsTransition(unittest.TestCase):

    def test_api_import(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            # Old API end point, no warning.
            from buildbot.plugins import buildslave as buildslave_ns
            # New API.
            from buildbot.plugins import worker as worker_ns
            # New API.
            self.assertTrue(worker_ns.Worker is buildbot.worker.Worker)

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"'buildbot\.plugins\.buildslave' plugins "
                                "namespace is deprecated"):
            # Old API, with warning
            self.assertTrue(
                buildslave_ns.BuildSlave is buildbot.worker.Worker)

        # Access of newly named workers through old entry point is an error.
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"'buildbot\.plugins\.buildslave' plugins "
                                "namespace is deprecated"):
            self.assertRaises(AttributeError, lambda: buildslave_ns.Worker)

        # Access of old-named workers through new API is an error.
        self.assertRaises(AttributeError, lambda: worker_ns.BuildSlave)

    def test_plugins_util_SlaveLock_import(self):
        from buildbot.plugins import util

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = util.WorkerLock

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=re.escape(
                    "'buildbot.util.SlaveLock' is deprecated, "
                    "use 'buildbot.util.WorkerLock' instead")):
            deprecated = util.SlaveLock

        self.assertIdentical(new, deprecated)

    def test_plugins_util_enforceChosenSlave_import(self):
        from buildbot.plugins import util

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = util.enforceChosenWorker

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=re.escape(
                    "'buildbot.util.enforceChosenSlave' is deprecated, "
                    "use 'buildbot.util.enforceChosenWorker' instead")):
            deprecated = util.enforceChosenSlave

        self.assertIdentical(new, deprecated)

    def test_plugins_util_BuildslaveChoiceParameter_import(self):
        from buildbot.plugins import util

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = util.WorkerChoiceParameter

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=re.escape(
                    "'buildbot.util.BuildslaveChoiceParameter' is deprecated, "
                    "use 'buildbot.util.WorkerChoiceParameter' instead")):
            deprecated = util.BuildslaveChoiceParameter

        self.assertIdentical(new, deprecated)
