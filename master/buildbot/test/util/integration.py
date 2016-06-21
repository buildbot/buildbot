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
from __future__ import print_function

import StringIO
import sys

from future.utils import itervalues
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import threadpool
from twisted.python.filepath import FilePath
from twisted.trial import unittest
from zope.interface import implementer

from buildbot.config import MasterConfig
from buildbot.interfaces import IConfigLoader
from buildbot.master import BuildMaster
from buildbot.plugins import worker
from buildbot.process.results import SUCCESS
from buildbot.process.results import statusToString
from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.test.util.db import RealDatabaseMixin

try:
    from buildbot_worker.bot import Worker
except ImportError:
    Worker = None


@implementer(IConfigLoader)
class DictLoader(object):

    def __init__(self, config_dict):
        self.config_dict = config_dict

    def loadConfig(self):
        return MasterConfig.loadFromDict(self.config_dict, '<dict>')


@defer.inlineCallbacks
def getMaster(case, reactor, config_dict):
    """
    Create a started ``BuildMaster`` with the given configuration.
    """
    basedir = FilePath(case.mktemp())
    basedir.createDirectory()

    assert 'db_url' not in config_dict

    # prepare the database for the test
    realdb = RealDatabaseMixin()
    yield realdb.setUpRealDatabase(table_names=RealDatabaseMixin.ALL_TABLES)
    config_dict['db_url'] = realdb.db_url

    master = BuildMaster(
        basedir.path, reactor=reactor, config_loader=DictLoader(config_dict))

    def stopReactor():
        raise RuntimeError(
            "master could not be started and wanted to stop the reactor!")
    master.stopReactor = stopReactor

    # TODO: Allow BuildMaster to transparently upgrade the database, at least
    # for tests.
    master.config.db['db_url'] = config_dict['db_url']
    yield master.db.setup(check_version=False)
    yield master.db.model.upgrade()
    master.db.setup = lambda: None

    yield master.startService()

    defer.returnValue(master)


class _RunMasterBase(unittest.TestCase):
    proto = "null"

    if Worker is None:
        skip = "buildbot-worker package is not installed"

    @defer.inlineCallbacks
    def setupConfig(self, config_dict, startWorker=True):
        """
        Setup and start a master configured
        by the function configFunc defined in the test module.
        @type config_dict: dict
        @param configFunc: The BuildmasterConfig dictionary.
        """
        if startWorker:
            if self.proto == 'pb':
                proto = {"pb": {"port": "tcp:0:interface=127.0.0.1"}}
                workerclass = worker.Worker
            elif self.proto == 'null':
                proto = {"null": {}}
                workerclass = worker.LocalWorker
            config_dict['workers'] = [workerclass("local1", "localpw")]
            config_dict['protocols'] = proto

        m = yield getMaster(self, self.reactor, config_dict)
        self.master = m
        # and shutdown the db threadpool, as is normally done at reactor stop
        self.addCleanup(m.db.pool.shutdown)
        self.addCleanup(m.stopService)

        if not startWorker:
            return

        if self.proto == 'pb':
            # We find out the worker port automatically
            workerPort = list(itervalues(m.pbmanager.dispatchers))[
                0].port.getHost().port

            # create a worker, and attach it to the master, it will be started, and stopped
            # along with the master
            worker_dir = FilePath(self.mktemp())
            worker_dir.createDirectory()
            self.w = Worker(
                "127.0.0.1", workerPort, "local1", "localpw", worker_dir.path,
                False)
        elif self.proto == 'null':
            self.w = None
        if self.w is not None:
            self.w.startService()
            self.addCleanup(self.w.stopService)

        @defer.inlineCallbacks
        def dump():
            if not self._passed:
                dump = StringIO.StringIO()
                print("FAILED! dumping build db for debug", file=dump)
                builds = yield self.master.data.get(("builds",))
                for build in builds:
                    yield self.printBuild(build, dump, withLogs=True)

                raise self.failureException(dump.getvalue())
        self.addCleanup(dump)

    @defer.inlineCallbacks
    def doForceBuild(self, wantSteps=False, wantProperties=False,
                     wantLogs=False, useChange=False):

        # force a build, and wait until it is finished
        d = defer.Deferred()

        # in order to allow trigger based integration tests
        # we wait until the first started build is finished
        self.firstBuildId = None

        def newCallback(_, data):
            if self.firstBuildId is None:
                self.firstBuildId = data['buildid']
                newConsumer.stopConsuming()

        def finishedCallback(_, data):
            if self.firstBuildId == data['buildid']:
                d.callback(data)

        newConsumer = yield self.master.mq.startConsuming(
            newCallback,
            ('builds', None, 'new'))

        finishedConsumer = yield self.master.mq.startConsuming(
            finishedCallback,
            ('builds', None, 'finished'))

        if useChange is False:
            # use data api to force a build
            yield self.master.data.control("force", {}, ("forceschedulers", "force"))
        else:
            # use data api to force a build, via a new change
            yield self.master.data.updates.addChange(**useChange)

        # wait until we receive the build finished event
        build = yield d
        finishedConsumer.stopConsuming()
        yield self.enrichBuild(build, wantSteps, wantProperties, wantLogs)
        defer.returnValue(build)

    @defer.inlineCallbacks
    def enrichBuild(self, build, wantSteps=False, wantProperties=False, wantLogs=False):
        # enrich the build result, with the step results
        if wantSteps:
            build["steps"] = yield self.master.data.get(("builds", build['buildid'], "steps"))
            # enrich the step result, with the logs results
            if wantLogs:
                build["steps"] = list(build["steps"])
                for step in build["steps"]:
                    step['logs'] = yield self.master.data.get(("steps", step['stepid'], "logs"))
                    step["logs"] = list(step['logs'])
                    for log in step["logs"]:
                        log['contents'] = yield self.master.data.get(("logs", log['logid'], "contents"))

        if wantProperties:
            build["properties"] = yield self.master.data.get(("builds", build['buildid'], "properties"))

    @defer.inlineCallbacks
    def printBuild(self, build, out=sys.stdout, withLogs=False):
        # helper for debugging: print a build
        yield self.enrichBuild(build, wantSteps=True, wantProperties=True, wantLogs=True)
        print("*** BUILD %d *** ==> %s (%s)" % (build['buildid'], build['state_string'],
                                                statusToString(build['results'])), file=out)
        for step in build['steps']:
            print("    *** STEP %s *** ==> %s (%s)" % (step['name'], step['state_string'],
                                                       statusToString(step['results'])), file=out)
            for url in step['urls']:
                print("       url:%s (%s)" %
                      (url['name'], url['url']), file=out)
            for log in step['logs']:
                print("        log:%s (%d)" %
                      (log['name'], log['num_lines']), file=out)
                if step['results'] != SUCCESS or withLogs:
                    self.printLog(log, out)

    def printLog(self, log, out):
        print(" " * 8 + "*********** LOG: %s *********" %
              (log['name'],), file=out)
        if log['type'] == 's':
            for line in log['contents']['content'].splitlines():
                linetype = line[0]
                line = line[1:]
                if linetype == 'h':
                    # cyan
                    line = "\x1b[36m" + line + "\x1b[0m"
                if linetype == 'e':
                    # red
                    line = "\x1b[31m" + line + "\x1b[0m"
                print(" " * 8 + line)
        else:
            print(log['contents']['content'], file=out)
        print(" " * 8 + "********************************", file=out)


class RunMasterBase(_RunMasterBase, unittest.TestCase):

    reactor = reactor


class SyncRunMasterBase(_RunMasterBase, unittest.SynchronousTestCase):

    def setUp(self):
        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()
