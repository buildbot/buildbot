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

import mock
import os

import textwrap

from buildbot import config
from buildbot.master import BuildMaster
from buildbot.test.util import dirs
from buildbot.test.util import www
from buildslave.bot import BuildSlave
from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

# This integration test creates a master and slave environment, with one builder and a custom step
# The custom step is using a CustomService, in order to calculate its result
# we make sure that we can reconfigure the master while build is running


class RunMaster(dirs.DirsMixin, www.RequiresWwwMixin, unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath('basdir')
        self.setUpDirs(self.basedir)
        self.configfile = os.path.join(self.basedir, 'master.cfg')
        open(self.configfile, "w").write(textwrap.dedent("""
            from buildbot.test.integration.test_customservices import masterConfig
            BuildmasterConfig = masterConfig()
            """))

    def tearDown(self):
        return self.tearDownDirs()

    @defer.inlineCallbacks
    def do_test_master(self):
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

        slavePort = m.pbmanager.dispatchers.values()[0].port.getHost().port

        s = BuildSlave("127.0.0.1", slavePort, "local1", "localpw", self.basedir, False, False)
        s.setServiceParent(m)

        d = defer.Deferred()
        yield m.mq.startConsuming(lambda e, data: d.callback(data), ('buildsets', None, None))

        yield m.allSchedulers()[0].force("me")

        yield d

        # myService = m.namedServices['myService']
        # print myService.num_reconfig

        # stop the service
        yield m.stopService()

        # and shutdown the db threadpool, as is normally done at reactor stop
        m.db.pool.shutdown()

        # (trial will verify all reactor-based timers have been cleared, etc.)

    def test_master1(self):
        return self.do_test_master()

# master configuration

# Note that the *same* configuration objects are used for both runs of the
# master.  This is a more strenuous test than strictly required, since a master
# will generally re-execute master.cfg on startup.  However, it's good form and
# will help to flush out any bugs that may otherwise be difficult to find.

num_reconfig = 0


def masterConfig():
    global num_reconfig
    num_reconfig += 1
    c = {}
    from buildbot.buildslave import BuildSlave
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.schedulers.forcesched import ForceScheduler
    from buildbot.steps.shell import ShellCommand
    from buildbot.util.service import CustomService, CustomServiceFactory
    c['slaves'] = [BuildSlave("local1", "localpw")]
    c['protocols'] = {"pb": {"port": "tcp:0:interface=127.0.0.1"}}
    c['change_source'] = []
    c['schedulers'] = []
    c['schedulers'].append(ForceScheduler(
        name="force",
        builderNames=["testy"]))
    f1 = BuildFactory()
    f1.addStep(ShellCommand(command='echo hi'))
    c['builders'] = []
    c['builders'].append(
        BuilderConfig(name="testy",
                      slavenames=["local1"],
                      factory=f1))
    c['status'] = []
    c['title'] = "test"
    c['titleURL'] = "test"
    c['buildbotURL'] = "http://localhost:8010/"
    c['db'] = {
        'db_url': "sqlite:///state.sqlite"
    }

    class MyService(CustomService):

        def configureService(self, _num_reconfig):
            self.num_reconfig = _num_reconfig

    c['services'] = [CustomServiceFactory("myService", MyService, num_reconfig=num_reconfig)]
    return c
