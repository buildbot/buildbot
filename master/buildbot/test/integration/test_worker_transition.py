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
from buildbot.util import unicode2bytes
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning

# Template for master configuration after renaming.
sample_0_9_0b5_api_renamed = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['workers'] = [worker.Worker("example-worker", "pass")]

c['protocols'] = {'pb': {'port': 'tcp:0'}}

c['change_source'] = []
c['change_source'].append(changes.GitPoller(
        'https://github.com/buildbot/hello-world.git',
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
factory.addStep(steps.Git(repourl='https://github.com/buildbot/hello-world.git', mode='incremental'))
factory.addStep(steps.ShellCommand(command=["trial", "hello"],
                                   env={"PYTHONPATH": "."}))

c['builders'] = []
c['builders'].append(
    util.BuilderConfig(name="runtests",
      workernames=["example-worker"],
      factory=factory))

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
    def test_config_0_9_0b5_api_renamed(self):
        # Load configuration and start master.
        # TODO: check for expected warnings.

        configfile = self._write_config(sample_0_9_0b5_api_renamed)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            _, loaded_config = config.loadConfigDict(".", configfile.path)

            yield self._run_master(loaded_config)
