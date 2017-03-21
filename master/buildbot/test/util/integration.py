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
from __future__ import division
from __future__ import print_function
from future.utils import itervalues

import sys
from io import StringIO

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python.filepath import FilePath
from twisted.trial import unittest
from zope.interface import implementer

from buildbot.config import MasterConfig
from buildbot.data import resultspec
from buildbot.interfaces import IConfigLoader
from buildbot.master import BuildMaster
from buildbot.plugins import worker
from buildbot.process.results import SUCCESS
from buildbot.process.results import statusToString

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
    config_dict['buildbotNetUsageData'] = None
    master = BuildMaster(
        basedir.path, reactor=reactor, config_loader=DictLoader(config_dict))

    if 'db_url' not in config_dict:
        config_dict['db_url'] = 'sqlite://'

    # TODO: Allow BuildMaster to transparently upgrade the database, at least
    # for tests.
    master.config.db['db_url'] = config_dict['db_url']
    yield master.db.setup(check_version=False)
    yield master.db.model.upgrade()
    master.db.setup = lambda: None

    yield master.startService()
    # and shutdown the db threadpool, as is normally done at reactor stop
    case.addCleanup(master.db.pool.shutdown)
    case.addCleanup(master.stopService)

    defer.returnValue(master)


class RunMasterBase(unittest.TestCase):
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
        # mock reactor.stop (which trial *really* doesn't
        # like test code to call!)
        stop = mock.create_autospec(reactor.stop)
        self.patch(reactor, 'stop', stop)

        if startWorker:
            if self.proto == 'pb':
                proto = {"pb": {"port": "tcp:0:interface=127.0.0.1"}}
                workerclass = worker.Worker
            elif self.proto == 'null':
                proto = {"null": {}}
                workerclass = worker.LocalWorker
            config_dict['workers'] = [workerclass("local1", "localpw")]
            config_dict['protocols'] = proto

        m = yield getMaster(self, reactor, config_dict)
        self.master = m
        self.assertFalse(stop.called,
                         "startService tried to stop the reactor; check logs")

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
                dump = StringIO()
                print(u"FAILED! dumping build db for debug", file=dump)
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
        self.firstBuildRequestId = None

        def newCallback(_, data):
            if self.firstBuildRequestId is None:
                self.firstBuildRequestId = data['buildrequestid']
                newConsumer.stopConsuming()

        def finishedCallback(_, data):
            if self.firstBuildRequestId == data['buildrequestid']:
                d.callback(data)

        newConsumer = yield self.master.mq.startConsuming(
            newCallback,
            ('buildrequests', None, 'new'))

        finishedConsumer = yield self.master.mq.startConsuming(
            finishedCallback,
            ('buildrequests', None, 'complete'))

        if useChange is False:
            # use data api to force a build
            yield self.master.data.control("force", {}, ("forceschedulers", "force"))
        else:
            # use data api to force a build, via a new change
            yield self.master.data.updates.addChange(**useChange)

        # wait until we receive the build finished event
        buildrequest = yield d
        builds = yield self.master.data.get(
            ('builds',),
            filters=[resultspec.Filter('buildrequestid', 'eq', [buildrequest['buildrequestid']])])
        # if the build has been retried, there will be several matching builds.
        # We return the last build
        build = builds[-1]
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
        print(u"*** BUILD %d *** ==> %s (%s)" % (build['buildid'], build['state_string'],
                                                 statusToString(build['results'])), file=out)
        for step in build['steps']:
            print(u"    *** STEP %s *** ==> %s (%s)" % (step['name'], step['state_string'],
                                                        statusToString(step['results'])), file=out)
            for url in step['urls']:
                print(u"       url:%s (%s)" %
                      (url['name'], url['url']), file=out)
            for log in step['logs']:
                print(u"        log:%s (%d)" %
                      (log['name'], log['num_lines']), file=out)
                if step['results'] != SUCCESS or withLogs:
                    self.printLog(log, out)

    @defer.inlineCallbacks
    def checkBuildStepLogExist(self, build, expectedLog, onlyStdout=False):
        yield self.enrichBuild(build, wantSteps=True, wantProperties=True, wantLogs=True)
        for step in build['steps']:
            for log in step['logs']:
                for line in log['contents']['content'].splitlines():
                    if onlyStdout and line[0] != 'o':
                        continue
                    if expectedLog in line:
                        defer.returnValue(True)
        defer.returnValue(False)

    def printLog(self, log, out):
        print(u" " * 8 + "*********** LOG: %s *********" %
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
                print(u" " * 8 + line)
        else:
            print(u"" + log['contents']['content'], file=out)
        print(u" " * 8 + "********************************", file=out)
