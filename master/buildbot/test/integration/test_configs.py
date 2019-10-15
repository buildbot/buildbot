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

from twisted.python import util
from twisted.trial import unittest

from buildbot import config
from buildbot.scripts import runner
from buildbot.test.util import dirs
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.worker_transition import DeprecatedWorkerAPIWarning


class RealConfigs(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpDirs('basedir')
        self.basedir = os.path.abspath('basedir')
        self.filename = os.path.abspath("test.cfg")

    def tearDown(self):
        self.tearDownDirs()

    def test_sample_config(self):
        filename = util.sibpath(runner.__file__, 'sample.cfg')
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            config.FileLoader(self.basedir, filename).loadConfig()

    def test_0_9_0b5_api_renamed_config(self):
        with open(self.filename, "w") as f:
            f.write(sample_0_9_0b5_api_renamed)
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            config.FileLoader(self.basedir, self.filename).loadConfig()


# sample.cfg from various versions, with comments stripped.  Adjustments made
# for compatibility are marked with comments

# Template for master configuration just after worker renaming.
sample_0_9_0b5_api_renamed = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['workers'] = [worker.Worker("example-worker", "pass")]

c['protocols'] = {'pb': {'port': 9989}}

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

c['www'] = dict(port=8010,
                plugins=dict(waterfall_view={}, console_view={}))

c['db'] = {
    'db_url' : "sqlite:///state.sqlite",
}
"""
