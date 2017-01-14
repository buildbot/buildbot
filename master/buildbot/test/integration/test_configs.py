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

from twisted.python import util
from twisted.trial import unittest

from buildbot import config
from buildbot.scripts import runner
from buildbot.test.util import dirs
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


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

    def test_0_9_0b5_config(self):
        with open(self.filename, "w") as f:
            f.write(sample_0_9_0b5)
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"'buildbot\.plugins\.buildslave' plugins namespace is deprecated",
                    r"'slavenames' keyword argument is deprecated",
                    r"c\['slaves'\] key is deprecated"]):
            config.FileLoader(self.basedir, self.filename).loadConfig()

    def test_0_7_12_config(self):
        with open(self.filename, "w") as f:
            f.write(sample_0_7_12)
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"BuildSlave was deprecated",
                    r"c\['slavePortnum'\] key is deprecated",
                    r"'slavename' keyword argument is deprecated",
                    r"c\['slaves'\] key is deprecated"]):
            config.FileLoader(self.basedir, self.filename).loadConfig()

    def test_0_7_6_config(self):
        with open(self.filename, "w") as f:
            f.write(sample_0_7_6)
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"BuildSlave was deprecated",
                    r"c\['slavePortnum'\] key is deprecated",
                    r"'slavename' keyword argument is deprecated",
                    r"c\['slaves'\] key is deprecated"]):
            config.FileLoader(self.basedir, self.filename).loadConfig()


# sample.cfg from various versions, with comments stripped.  Adjustments made
# for compatibility are marked with comments

sample_0_7_6 = """\
c = BuildmasterConfig = {}
from buildbot.buildslave import BuildSlave
c['slaves'] = [BuildSlave("bot1name", "bot1passwd")]
c['slavePortnum'] = 9989
from buildbot.changes.pb import PBChangeSource
c['change_source'] = PBChangeSource()
from buildbot.scheduler import Scheduler
c['schedulers'] = []
c['schedulers'].append(Scheduler(name="all", branch=None,
                                 treeStableTimer=2*60,
                                 builderNames=["buildbot-full"]))
cvsroot = ":pserver:anonymous@cvs.sourceforge.net:/cvsroot/buildbot"
cvsmodule = "buildbot"
from buildbot.process import factory
from buildbot.steps.python_twisted import Trial
from buildbot.steps.shell import Compile
from buildbot.steps.source.cvs import CVS
f1 = factory.BuildFactory()
f1.addStep(CVS(cvsroot=cvsroot, cvsmodule=cvsmodule, login="", method="copy"))
f1.addStep(Compile(command=["python", "./setup.py", "build"]))
# original lacked testChanges=True; this failed at the time
f1.addStep(Trial(testChanges=True, testpath="."))
b1 = {'name': "buildbot-full",
      'slavename': "bot1name",
      'builddir': "full",
      'factory': f1,
      }
c['builders'] = [b1]
c['status'] = []
# WebStatus is dead.
#from buildbot.status import html
#c['status'].append(html.WebStatus(http_port=8010))
c['projectName'] = "Buildbot"
c['projectURL'] = "http://buildbot.sourceforge.net/"
c['buildbotURL'] = "http://localhost:8010/"
"""

sample_0_7_12 = """\
c = BuildmasterConfig = {}
from buildbot.buildslave import BuildSlave
c['slaves'] = [BuildSlave("bot1name", "bot1passwd")]
c['slavePortnum'] = 9989
from buildbot.changes.pb import PBChangeSource
c['change_source'] = PBChangeSource()
from buildbot.scheduler import Scheduler
c['schedulers'] = []
c['schedulers'].append(Scheduler(name="all", branch=None,
                                 treeStableTimer=2*60,
                                 builderNames=["buildbot-full"]))
cvsroot = ":pserver:anonymous@cvs.sourceforge.net:/cvsroot/buildbot"
cvsmodule = "buildbot"
from buildbot.process import factory
# old source is deprecated, so we use the new source
from buildbot.steps.python_twisted import Trial
from buildbot.steps.shell import Compile
from buildbot.steps.source.cvs import CVS
f1 = factory.BuildFactory()
f1.addStep(CVS(cvsroot=cvsroot, cvsmodule=cvsmodule, login="", method="copy"))
f1.addStep(Compile(command=["python", "./setup.py", "build"]))
f1.addStep(Trial(testChanges=True, testpath="."))
b1 = {'name': "buildbot-full",
      'slavename': "bot1name",
      'builddir': "full",
      'factory': f1,
      }
c['builders'] = [b1]
c['status'] = []
# WebStatus is dead.
#from buildbot.status import html
#c['status'].append(html.WebStatus(http_port=8010))
c['projectName'] = "Buildbot"
c['projectURL'] = "http://buildbot.sourceforge.net/"
c['buildbotURL'] = "http://localhost:8010/"
"""

# Template for master configuration just before worker renaming.
sample_0_9_0b5 = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['slaves'] = [buildslave.BuildSlave("example-slave", "pass")]

c['protocols'] = {'pb': {'port': 9989}}

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

c['buildbotURL'] = "http://localhost:8020/"

c['www'] = dict(port=8010,
                plugins=dict(waterfall_view={}, console_view={}))

c['db'] = {
    'db_url' : "sqlite:///state.sqlite",
}
"""

# Template for master configuration just after worker renaming.
sample_0_9_0b5_api_renamed = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['workers'] = [worker.Worker("example-worker", "pass")]

c['protocols'] = {'pb': {'port': 9989}}

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

c['www'] = dict(port=8010,
                plugins=dict(waterfall_view={}, console_view={}))

c['db'] = {
    'db_url' : "sqlite:///state.sqlite",
}
"""
