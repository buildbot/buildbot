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

import re

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.task import deferLater
from twisted.python.filepath import FilePath
from twisted.trial import unittest
from zope.interface import implementer

import buildbot.worker
from buildbot import config
from buildbot.interfaces import IConfigLoader
from buildbot.test.util import www
from buildbot.test.util.integration import RunMasterBase
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.util import unicode2bytes
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
"""


@implementer(IConfigLoader)
class DummyLoader(object):

    def __init__(self, loaded_config):
        self.loaded_config = loaded_config

    def loadConfig(self):
        return self.loaded_config


class RunMaster(RunMasterBase, www.RequiresWwwMixin):

    """Test that master can actually run with configuration after renaming."""

    @defer.inlineCallbacks
    def _run_master(self, loaded_config):
        # mock reactor.stop (which trial *really* doesn't
        # like test code to call!)
        yield self.setupConfig(loaded_config, startWorker=False)

        # hang out for a fraction of a second, to let startup processes run
        yield deferLater(reactor, 0.01, lambda: None)

    def _write_config(self, config_str):
        config_bytes = unicode2bytes(config_str)
        configfile = FilePath(self.mktemp())
        configfile.setContent(config_bytes)
        return configfile

    @defer.inlineCallbacks
    def test_config_0_9_0b5(self):
        # Load configuration and start master.
        # TODO: check for expected warnings.
        configfile = self._write_config(sample_0_9_0b5)

        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"'buildbot\.plugins\.buildslave' plugins namespace is deprecated",
                    r"'slavenames' keyword argument is deprecated",
                    r"c\['slaves'\] key is deprecated"]):
            _, loaded_config = config.loadConfigDict(".", configfile.path)

            yield self._run_master(loaded_config)

    @defer.inlineCallbacks
    def test_config_0_9_0b5_api_renamed(self):
        # Load configuration and start master.
        # TODO: check for expected warnings.

        configfile = self._write_config(sample_0_9_0b5_api_renamed)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            _, loaded_config = config.loadConfigDict(".", configfile.path)

            yield self._run_master(loaded_config)


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
