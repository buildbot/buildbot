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


from twisted.internet import defer

from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.process.workerforbuilder import PingException
from buildbot.test.fake.worker import WorkerController
from buildbot.test.util.integration import RunFakeMasterTestCase


class Tests(RunFakeMasterTestCase):

    @defer.inlineCallbacks
    def do_terminates_ping_on_shutdown(self, quick_mode):
        """
        During shutdown we want to terminate any outstanding pings.
        """
        controller = WorkerController(self, 'local')

        config_dict = {
            'builders': [
                BuilderConfig(name="testy",
                              workernames=['local'],
                              factory=BuildFactory()),
            ],
            'workers': [controller.worker],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder_id = yield master.data.updates.findBuilderId('testy')

        controller.connect_worker()
        controller.sever_connection()
        yield self.createBuildrequest(master, [builder_id])

        # give time for any delayed actions to complete
        self.reactor.advance(1)

        yield master.botmaster.cleanShutdown(quickMode=quick_mode, stopReactor=False)
        self.flushLoggedErrors(PingException)

    def test_terminates_ping_on_shutdown_quick_mode(self):
        return self.do_terminates_ping_on_shutdown(quick_mode=True)

    def test_terminates_ping_on_shutdown_slow_mode(self):
        return self.do_terminates_ping_on_shutdown(quick_mode=False)
