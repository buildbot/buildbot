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
from __future__ import annotations

import os
import re
import sys
from io import StringIO
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.python.filepath import FilePath
from twisted.trial import unittest
from zope.interface import implementer

from buildbot.config.master import MasterConfig
from buildbot.data import resultspec
from buildbot.interfaces import IConfigLoader
from buildbot.master import BuildMaster
from buildbot.plugins import worker
from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.process.results import statusToString
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.misc import DebugIntegrationLogsMixin
from buildbot.test.util.sandboxed_worker import SandboxedWorker
from buildbot.util.twisted import any_to_async
from buildbot.util.twisted import async_to_deferred
from buildbot.worker.local import LocalWorker
from buildbot_worker.bot import Worker

if TYPE_CHECKING:
    from twisted.application.service import Service


@implementer(IConfigLoader)
class DictLoader:
    def __init__(self, config_dict):
        self.config_dict = config_dict

    def loadConfig(self):
        return MasterConfig.loadFromDict(self.config_dict, '<dict>')


class TestedMaster:
    def __init__(self) -> None:
        self.master: BuildMaster | None = None
        self.is_master_shutdown = False

    @async_to_deferred
    async def create_master(self, case, reactor, config_dict, basedir=None):
        """
        Create a started ``BuildMaster`` with the given configuration.
        """
        if basedir is None:
            basedir = case.mktemp()
        os.makedirs(basedir, exist_ok=True)
        config_dict['buildbotNetUsageData'] = None
        self.master = BuildMaster(basedir, reactor=reactor, config_loader=DictLoader(config_dict))

        if 'db_url' not in config_dict:
            config_dict['db_url'] = 'sqlite://'

        # TODO: Allow BuildMaster to transparently upgrade the database, at least
        # for tests.
        self.master.config.db.db_url = config_dict['db_url']
        await self.master.db.setup(check_version=False)
        await self.master.db.model.upgrade()
        self.master.db.setup = lambda: None

        await self.master.startService()

        case.addCleanup(self.shutdown)

        return self.master

    @async_to_deferred
    async def shutdown(self):
        if self.is_master_shutdown:
            return
        try:
            await self.master.stopService()
        except Exception as e:
            log.err(e)
        try:
            await self.master.db.pool.stop()
        except Exception as e:
            log.err(e)
        self.is_master_shutdown = True


def print_test_log(l, out):
    print(" " * 8 + f"*********** LOG: {l['name']} *********", file=out)
    if l['type'] == 's':
        for line in l['contents']['content'].splitlines():
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
        print("" + l['contents']['content'], file=out)
    print(" " * 8 + "********************************", file=out)


@async_to_deferred
async def enrich_build(
    build, master: BuildMaster, want_steps=False, want_properties=False, want_logs=False
):
    # enrich the build result, with the step results
    if want_steps:
        build["steps"] = await master.data.get(("builds", build['buildid'], "steps"))
        # enrich the step result, with the logs results
        if want_logs:
            build["steps"] = list(build["steps"])
            for step in build["steps"]:
                step['logs'] = await master.data.get(("steps", step['stepid'], "logs"))
                step["logs"] = list(step['logs'])
                for l in step["logs"]:
                    l['contents'] = await master.data.get((
                        "logs",
                        l['logid'],
                        "contents",
                    ))

    if want_properties:
        build["properties"] = await master.data.get((
            "builds",
            build['buildid'],
            "properties",
        ))


@async_to_deferred
async def print_build(build, master: BuildMaster, out=sys.stdout, with_logs=False):
    # helper for debugging: print a build
    await enrich_build(build, master, want_steps=True, want_properties=True, want_logs=True)
    print(
        f"*** BUILD {build['buildid']} *** ==> {build['state_string']} "
        f"({statusToString(build['results'])})",
        file=out,
    )
    for step in build['steps']:
        print(
            f"    *** STEP {step['name']} *** ==> {step['state_string']} "
            f"({statusToString(step['results'])})",
            file=out,
        )
        for url in step['urls']:
            print(f"       url:{url['name']} ({url['url']})", file=out)
        for l in step['logs']:
            print(f"        log:{l['name']} ({l['num_lines']})", file=out)
            if step['results'] != SUCCESS or with_logs:
                print_test_log(l, out)


class RunFakeMasterTestCase(TestReactorMixin, DebugIntegrationLogsMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.setupDebugIntegrationLogs()

        def cleanup():
            self.assertFalse(self.master.running, "master is still running!")

        self.addCleanup(cleanup)

    @defer.inlineCallbacks
    def setup_master(self, config_dict):
        self.tested_master = TestedMaster()
        self.master = yield self.tested_master.create_master(self, self.reactor, config_dict)

    @defer.inlineCallbacks
    def reconfig_master(self, config_dict=None):
        if config_dict is not None:
            self.master.config_loader.config_dict = config_dict
        yield self.master.doReconfig()

    @defer.inlineCallbacks
    def clean_master_shutdown(self, quick=False):
        yield self.master.botmaster.cleanShutdown(quickMode=quick, stopReactor=False)

    def createLocalWorker(self, name, **kwargs):
        workdir = FilePath(self.mktemp())
        workdir.createDirectory()
        return LocalWorker(name, workdir.path, **kwargs)

    @defer.inlineCallbacks
    def assertBuildResults(self, build_id, result):
        dbdict = yield self.master.db.builds.getBuild(build_id)
        self.assertEqual(result, dbdict.results)

    @defer.inlineCallbacks
    def assertStepStateString(self, step_id, state_string):
        datadict = yield self.master.data.get(('steps', step_id))
        self.assertEqual(datadict['state_string'], state_string)

    @defer.inlineCallbacks
    def assertLogs(self, build_id, exp_logs):
        got_logs = {}
        data_logs = yield self.master.data.get(('builds', build_id, 'steps', 1, 'logs'))
        for l in data_logs:
            self.assertTrue(l['complete'])
            log_contents = yield self.master.data.get((
                'builds',
                build_id,
                'steps',
                1,
                'logs',
                l['slug'],
                'contents',
            ))

            got_logs[l['name']] = log_contents['content']

        self.assertEqual(got_logs, exp_logs)

    @defer.inlineCallbacks
    def create_build_request(self, builder_ids, properties=None):
        properties = properties.asDict() if properties is not None else None
        ret = yield self.master.data.updates.addBuildset(
            waited_for=False,
            builderids=builder_ids,
            sourcestamps=[
                {'codebase': '', 'repository': '', 'branch': None, 'revision': None, 'project': ''},
            ],
            properties=properties,
        )
        # run debounced calls
        self.master.reactor.advance(1)
        return ret

    @defer.inlineCallbacks
    def do_test_build_by_name(self, builder_name):
        builder_id = yield self.master.data.updates.findBuilderId(builder_name)
        yield self.do_test_build(builder_id)

    @defer.inlineCallbacks
    def do_test_build(self, builder_id):
        # setup waiting for build to finish
        d_finished = defer.Deferred()

        def on_finished(_, __):
            if not d_finished.called:
                d_finished.callback(None)

        consumer = yield self.master.mq.startConsuming(on_finished, ('builds', None, 'finished'))

        # start the builder
        yield self.create_build_request([builder_id])

        # and wait for build completion
        yield d_finished
        yield consumer.stopConsuming()


class TestedRealMaster(TestedMaster):
    def __init__(self) -> None:
        super().__init__()
        self.case: unittest.TestCase | None = None
        self.worker: Service | None = None

    @async_to_deferred
    async def setup_master(
        self,
        case: unittest.TestCase,
        reactor,
        config_dict,
        proto='null',
        basedir=None,
        start_worker=True,
        **worker_kwargs,
    ):
        """
        Setup and start a master configured by config_dict
        """

        self.case = case

        # mock reactor.stop (which trial *really* doesn't like test code to call!)
        stop = mock.create_autospec(reactor.stop)
        case.patch(reactor, 'stop', stop)

        if start_worker:
            config_protocols: dict[str, Any] = {}
            if proto == 'pb':
                config_protocols = {"pb": {"port": "tcp:0:interface=127.0.0.1"}}
                workerclass = worker.Worker
            elif proto == 'msgpack':
                config_protocols = {"msgpack_experimental_v7": {"port": 0}}
                workerclass = worker.Worker
            elif proto == 'null':
                config_protocols = {"null": {}}
                workerclass = worker.LocalWorker
            else:
                raise RuntimeError(f"{proto} protocol is not supported.")
            config_dict['workers'] = [
                workerclass("local1", password=Interpolate("localpw"), missing_timeout=0)
            ]
            config_dict['protocols'] = config_protocols

        await self.create_master(case, reactor, config_dict, basedir=basedir)
        self.master_config_dict = config_dict
        case.assertFalse(stop.called, "startService tried to stop the reactor; check logs")

        if not start_worker:
            return

        assert self.master
        if proto in ('pb', 'msgpack'):
            sandboxed_worker_path = os.environ.get("SANDBOXED_WORKER_PATH", None)
            if proto == 'pb':
                protocol = 'pb'
                dispatcher = next(iter(self.master.pbmanager.dispatchers.values()))
            else:
                protocol = 'msgpack_experimental_v7'
                dispatcher = next(iter(self.master.msgmanager.dispatchers.values()))

                # We currently don't handle connection closing cleanly.
                dispatcher.serverFactory.setProtocolOptions(closeHandshakeTimeout=0)

            worker_port = dispatcher.port.getHost().port

            # create a worker, and attach it to the master, it will be started, and stopped
            # along with the master
            worker_dir = FilePath(case.mktemp())
            worker_dir.createDirectory()
            if sandboxed_worker_path is None:
                self.worker = Worker(
                    "127.0.0.1",
                    worker_port,
                    "local1",
                    "localpw",
                    worker_dir.path,
                    False,
                    protocol=protocol,
                    **worker_kwargs,
                )
            else:
                self.worker = SandboxedWorker(
                    "127.0.0.1",
                    worker_port,
                    "local1",
                    "localpw",
                    worker_dir.path,
                    sandboxed_worker_path,
                    protocol=protocol,
                    **worker_kwargs,
                )

        if self.worker is not None:
            await any_to_async(self.worker.setServiceParent(self.master))

        case.addCleanup(self.dump_data_if_failed)

    @async_to_deferred
    async def shutdown(self):
        if self.is_master_shutdown:
            return

        if isinstance(self.worker, SandboxedWorker):
            try:
                await self.worker.shutdownWorker()
            except Exception as e:
                log.err(e)
        await super().shutdown()

    @async_to_deferred
    async def dump_data_if_failed(self):
        if self.case is not None and not self.case._passed and not self.is_master_shutdown:
            dump = StringIO()
            print("FAILED! dumping build db for debug", file=dump)
            builds = await self.master.data.get(("builds",))
            for build in builds:
                await print_build(build, self.master, dump, with_logs=True)

            raise self.case.failureException(dump.getvalue())


class RunMasterBase(unittest.TestCase):
    proto = "null"

    # All tests that start master need higher timeout due to test runtime variability on
    # oversubscribed hosts.
    timeout = 60

    @defer.inlineCallbacks
    def setup_master(self, config_dict, startWorker=True, basedir=None, **worker_kwargs):
        self.tested_master = TestedRealMaster()
        yield self.tested_master.setup_master(
            self,
            reactor,
            config_dict,
            proto=self.proto,
            basedir=basedir,
            start_worker=startWorker,
            **worker_kwargs,
        )
        self.master = self.tested_master.master
        self.master_config_dict = self.tested_master.master_config_dict

    @defer.inlineCallbacks
    def doForceBuild(
        self,
        wantSteps=False,
        wantProperties=False,
        wantLogs=False,
        useChange=False,
        forceParams=None,
        triggerCallback=None,
    ):
        if forceParams is None:
            forceParams = {}
        # force a build, and wait until it is finished
        d = defer.Deferred()

        # in order to allow trigger based integration tests
        # we wait until the first started build is finished
        self.firstbsid = None

        def newCallback(_, data):
            if self.firstbsid is None:
                self.firstbsid = data['bsid']
                newConsumer.stopConsuming()

        def finishedCallback(_, data):
            if self.firstbsid == data['bsid']:
                d.callback(data)

        newConsumer = yield self.master.mq.startConsuming(newCallback, ('buildsets', None, 'new'))

        finishedConsumer = yield self.master.mq.startConsuming(
            finishedCallback, ('buildsets', None, 'complete')
        )

        if triggerCallback is not None:
            yield triggerCallback()
        elif useChange is False:
            # use data api to force a build
            yield self.master.data.control("force", forceParams, ("forceschedulers", "force"))
        else:
            # use data api to force a build, via a new change
            yield self.master.data.updates.addChange(**useChange)

        # wait until we receive the build finished event
        buildset = yield d
        buildrequests = yield self.master.data.get(
            ('buildrequests',), filters=[resultspec.Filter('buildsetid', 'eq', [buildset['bsid']])]
        )
        buildrequest = buildrequests[-1]
        builds = yield self.master.data.get(
            ('builds',),
            filters=[resultspec.Filter('buildrequestid', 'eq', [buildrequest['buildrequestid']])],
        )
        # if the build has been retried, there will be several matching builds.
        # We return the last build
        build = builds[-1]
        finishedConsumer.stopConsuming()
        yield enrich_build(build, self.master, wantSteps, wantProperties, wantLogs)
        return build

    def _match_patterns_consume(self, text, patterns, is_regex):
        for pattern in patterns[:]:
            if is_regex:
                if re.search(pattern, text):
                    patterns.remove(pattern)
            else:
                if pattern in text:
                    patterns.remove(pattern)
        return patterns

    @defer.inlineCallbacks
    def checkBuildStepLogExist(self, build, expectedLog, onlyStdout=False, regex=False):
        if isinstance(expectedLog, str):
            expectedLog = [expectedLog]
        if not isinstance(expectedLog, list):
            raise RuntimeError(
                'The expectedLog argument must be either string or a list of strings'
            )

        yield enrich_build(
            build, self.master, want_steps=True, want_properties=True, want_logs=True
        )
        for step in build['steps']:
            for l in step['logs']:
                for line in l['contents']['content'].splitlines():
                    if onlyStdout and line[0] != 'o':
                        continue
                    expectedLog = self._match_patterns_consume(line, expectedLog, is_regex=regex)
        if expectedLog:
            print(f"{expectedLog} not found in logs")
        return len(expectedLog) == 0
