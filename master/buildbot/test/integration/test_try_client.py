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

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.python.filepath import FilePath

from buildbot import util
from buildbot.clients import tryclient
from buildbot.schedulers import trysched
from buildbot.test.util import www
from buildbot.test.util.integration import RunMasterBase


# wait for some asynchronous result
@defer.inlineCallbacks
def waitFor(fn):
    while True:
        res = yield fn()
        if res:
            return res
        yield util.asyncSleep(.01)


class Schedulers(RunMasterBase, www.RequiresWwwMixin):

    def setUp(self):
        self.master = None
        self.sch = None

        def spawnProcess(pp, executable, args, environ):
            tmpfile = os.path.join(self.jobdir, 'tmp', 'testy')
            newfile = os.path.join(self.jobdir, 'new', 'testy')
            with open(tmpfile, "w", encoding='utf-8') as f:
                f.write(pp.job)
            os.rename(tmpfile, newfile)
            log.msg(f"wrote jobfile {newfile}")
            # get the scheduler to poll this directory now
            d = self.sch.watcher.poll()
            d.addErrback(log.err, 'while polling')

            @d.addCallback
            def finished(_):
                st = mock.Mock()
                st.value.signal = None
                st.value.exitCode = 0
                pp.processEnded(st)

        self.patch(reactor, 'spawnProcess', spawnProcess)

        self.sourcestamp = tryclient.SourceStamp(branch='br', revision='rr', patch=(0, '++--'))

        def getSourceStamp(vctype, treetop, branch=None, repository=None):
            return defer.succeed(self.sourcestamp)
        self.patch(tryclient, 'getSourceStamp', getSourceStamp)

        self.output = []

        # stub out printStatus, as it's timing-based and thus causes
        # occasional test failures.
        self.patch(tryclient.Try, 'printStatus', lambda _: None)

        def output(*msg):
            msg = ' '.join(map(str, msg))
            log.msg(f"output: {msg}")
            self.output.append(msg)
        self.patch(tryclient, 'output', output)

    def setupJobdir(self):
        jobdir = FilePath(self.mktemp())
        jobdir.createDirectory()
        self.jobdir = jobdir.path
        for sub in 'new', 'tmp', 'cur':
            jobdir.child(sub).createDirectory()
        return self.jobdir

    @defer.inlineCallbacks
    def startMaster(self, sch):
        extra_config = {
            'schedulers': [sch],
        }
        self.sch = sch

        yield self.setupConfig(masterConfig(extra_config))

        # wait until the scheduler is active
        yield waitFor(lambda: self.sch.active)

        # and, for Try_Userpass, until it's registered its port
        if isinstance(self.sch, trysched.Try_Userpass):
            def getSchedulerPort():
                if not self.sch.registrations:
                    return None
                self.serverPort = self.sch.registrations[0].getPort()
                log.msg(f"Scheduler registered at port {self.serverPort}")
                return True
            yield waitFor(getSchedulerPort)

    def runClient(self, config):
        self.clt = tryclient.Try(config)
        return self.clt.run_impl()

    @defer.inlineCallbacks
    def test_userpass_no_wait(self):
        yield self.startMaster(
            trysched.Try_Userpass('try', ['a'], 0, [('u', b'p')]))
        yield self.runClient({
            'connect': 'pb',
            'master': f'127.0.0.1:{self.serverPort}',
            'username': 'u',
            'passwd': b'p',
        })
        self.assertEqual(self.output, [
            "using 'pb' connect method",
            'job created',
            'Delivering job; comment= None',
            'job has been delivered',
            'not waiting for builds to finish'
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)

    @defer.inlineCallbacks
    def test_userpass_wait(self):
        yield self.startMaster(
            trysched.Try_Userpass('try', ['a'], 0, [('u', b'p')]))
        yield self.runClient({
            'connect': 'pb',
            'master': f'127.0.0.1:{self.serverPort}',
            'username': 'u',
            'passwd': b'p',
            'wait': True,
        })
        self.assertEqual(self.output, [
            "using 'pb' connect method",
            'job created',
            'Delivering job; comment= None',
            'job has been delivered',
            'All Builds Complete',
            'a: success (build successful)',
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)

    @defer.inlineCallbacks
    def test_userpass_wait_bytes(self):
        self.sourcestamp = tryclient.SourceStamp(branch=b'br', revision=b'rr', patch=(0, b'++--'))

        yield self.startMaster(
            trysched.Try_Userpass('try', ['a'], 0, [('u', b'p')]))
        yield self.runClient({
            'connect': 'pb',
            'master': f'127.0.0.1:{self.serverPort}',
            'username': 'u',
            'passwd': b'p',
            'wait': True,
        })
        self.assertEqual(self.output, [
            "using 'pb' connect method",
            'job created',
            'Delivering job; comment= None',
            'job has been delivered',
            'All Builds Complete',
            'a: success (build successful)',
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)

    @defer.inlineCallbacks
    def test_userpass_wait_dryrun(self):
        yield self.startMaster(
            trysched.Try_Userpass('try', ['a'], 0, [('u', b'p')]))
        yield self.runClient({
            'connect': 'pb',
            'master': f'127.0.0.1:{self.serverPort}',
            'username': 'u',
            'passwd': b'p',
            'wait': True,
            'dryrun': True,
        })
        self.assertEqual(self.output, [
            "using 'pb' connect method",
            'job created',
            'Job:\n'
            '\tRepository: \n'
            '\tProject: \n'
            '\tBranch: br\n'
            '\tRevision: rr\n'
            '\tBuilders: None\n'
            '++--',
            'job has been delivered',
            'All Builds Complete',
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 0)

    @defer.inlineCallbacks
    def test_userpass_list_builders(self):
        yield self.startMaster(
            trysched.Try_Userpass('try', ['a'], 0, [('u', b'p')]))
        yield self.runClient({
            'connect': 'pb',
            'get-builder-names': True,
            'master': f'127.0.0.1:{self.serverPort}',
            'username': 'u',
            'passwd': b'p',
        })
        self.assertEqual(self.output, [
            "using 'pb' connect method",
            'The following builders are available for the try scheduler: ',
            'a'
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 0)

    @defer.inlineCallbacks
    def test_jobdir_no_wait(self):
        jobdir = self.setupJobdir()
        yield self.startMaster(trysched.Try_Jobdir('try', ['a'], jobdir))
        yield self.runClient({
            'connect': 'ssh',
            'master': '127.0.0.1',
            'username': 'u',
            'passwd': b'p',
            'builders': 'a',  # appears to be required for ssh
        })
        self.assertEqual(self.output, [
            "using 'ssh' connect method",
            'job created',
            'job has been delivered',
            'not waiting for builds to finish'
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)

    @defer.inlineCallbacks
    def test_jobdir_wait(self):
        jobdir = self.setupJobdir()
        yield self.startMaster(trysched.Try_Jobdir('try', ['a'], jobdir))
        yield self.runClient({
            'connect': 'ssh',
            'wait': True,
            'host': '127.0.0.1',
            'username': 'u',
            'passwd': b'p',
            'builders': 'a',  # appears to be required for ssh
        })
        self.assertEqual(self.output, [
            "using 'ssh' connect method",
            'job created',
            'job has been delivered',
            'waiting for builds with ssh is not supported'
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)


def masterConfig(extra_config):
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.buildstep import BuildStep
    from buildbot.process.factory import BuildFactory
    from buildbot.process import results

    class MyBuildStep(BuildStep):

        def run(self):
            return results.SUCCESS

    c['change_source'] = []
    c['schedulers'] = []  # filled in above
    f1 = BuildFactory()
    f1.addStep(MyBuildStep(name='one'))
    f1.addStep(MyBuildStep(name='two'))
    c['builders'] = [
        BuilderConfig(name="a", workernames=["local1"], factory=f1),
    ]
    c['title'] = "test"
    c['titleURL'] = "test"
    c['buildbotURL'] = "http://localhost:8010/"
    c['mq'] = {'debug': True}
    # test wants to influence the config, but we still return a new config
    # each time
    c.update(extra_config)
    return c
