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

import contextlib
import mock
import os
import warnings

from buildbot import config
from buildbot.master import BuildMaster
from buildbot.test.util import dirs
from buildbot.test.util import www
from buildbot.worker import Worker
from buildbot.worker_transition import DeprecatedWorkerNameWarning
from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest


class RunMaster(dirs.DirsMixin, www.RequiresWwwMixin, unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath('basdir')
        self.setUpDirs(self.basedir)
        self.configfile = os.path.join(self.basedir, 'master.cfg')

    def tearDown(self):
        return self.tearDownDirs()

    @defer.inlineCallbacks
    def _run_master(self, config_str):
        with open(self.configfile, "w") as f:
            f.write(config_str)

        # create the master and set its config
        m = BuildMaster(self.basedir, self.configfile)
        m.config = config.MasterConfig.loadConfig(
            self.basedir, self.configfile)

        # update the DB
        yield m.db.setup(check_version=False)
        yield m.db.model.upgrade()

        # stub out m.db.setup since it was already called above
        m.db.setup = lambda: None

        # mock reactor.stop (which trial *really* doesn't
        # like test code to call!)
        mock_reactor = mock.Mock(spec=reactor)
        mock_reactor.callWhenRunning = reactor.callWhenRunning

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

    def test_config_0_9_0b5(self):
        # Load configuration and start master.
        # TODO: check for expected warnings.
        return self._run_master(sample_0_9_0b5)


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

c['buildbotURL'] = "http://localhost:8020/"

c['db'] = {
    'db_url' : "sqlite:///state.sqlite",
}
"""


# TODO: rename and move this utility class to commons?
class _TestBase(unittest.TestCase):

    @contextlib.contextmanager
    def _assertProducesWarning(self, num_warnings=1):
        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")

            yield

            # Verify some things
            self.assertEqual(len(w), num_warnings,
                             msg="Unexpected warnings:\n{0}".format(
                                 "\n".join(map(str, w))))
            for warning in w:
                self.assertTrue(issubclass(warning.category,
                                           DeprecatedWorkerNameWarning))
                self.assertIn("deprecated", str(warning.message))

    @contextlib.contextmanager
    def _assertNotProducesWarning(self):
        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")

            yield

            # Verify some things
            self.assertEqual(len(w), 0)


class PluginsTransition(_TestBase):

    def test_old_api_use(self):
        with self._assertNotProducesWarning():
            # ok, no warning
            from buildbot.plugins import buildslave

        with self._assertProducesWarning():
            # ok, but with warning
            w = buildslave.BuildSlave
            self.assertTrue(issubclass(w, Worker))
