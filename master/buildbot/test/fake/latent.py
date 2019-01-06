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
from twisted.python.filepath import FilePath
from twisted.trial.unittest import SkipTest

from buildbot.worker import AbstractLatentWorker

try:
    from buildbot_worker.bot import LocalWorker as RemoteWorker
    from buildbot_worker.base import BotBase
except ImportError:
    RemoteWorker = None


class LatentController(object):

    """
    A controller for ``ControllableLatentWorker``.

    https://glyph.twistedmatrix.com/2015/05/separate-your-fakes-and-your-inspectors.html
    """

    def __init__(self, case, name, kind=None, build_wait_timeout=600, **kwargs):
        self.case = case
        self.build_wait_timeout = build_wait_timeout
        self.worker = ControllableLatentWorker(name, self, **kwargs)
        self.remote_worker = None

        self.starting = False
        self.started = False
        self.stopping = False
        self.auto_stop_flag = False
        self.auto_start_flag = False
        self.auto_connect_worker = False

        self.kind = kind
        self._started_kind = None
        self._started_kind_deferred = None

    def auto_start(self, result):
        self.auto_start_flag = result
        if self.auto_start_flag and self.starting:
            self.start_instance(True)

    def start_instance(self, result):
        self.do_start_instance()
        d, self._start_deferred = self._start_deferred, None
        d.callback(result)

    def do_start_instance(self):
        assert self.starting
        assert not self.started or not self.remote_worker
        self.starting = False
        self.started = True
        if self.auto_connect_worker:
            self.connect_worker()

    def auto_stop(self, result):
        self.auto_stop_flag = result
        if self.auto_stop_flag and self.stopping:
            self.stop_instance(True)

    def stop_instance(self, result):
        self.do_stop_instance()
        d, self._stop_deferred = self._stop_deferred, None
        d.callback(result)

    def do_stop_instance(self):
        assert self.stopping
        self.stopping = False
        self._started_kind = None
        self.disconnect_worker()

    def connect_worker(self):
        if self.remote_worker is not None:
            return
        if RemoteWorker is None:
            raise SkipTest("buildbot-worker package is not installed")
        workdir = FilePath(self.case.mktemp())
        workdir.createDirectory()
        self.remote_worker = RemoteWorker(self.worker.name, workdir.path, False)
        self.remote_worker.setServiceParent(self.worker)

    def disconnect_worker(self):
        if self.remote_worker is None:
            return
        self.worker.conn, conn = None, self.worker.conn
        # LocalWorker does actually disconnect, so we must force disconnection via detached
        conn.notifyDisconnected()
        ret = self.remote_worker.disownServiceParent()
        self.remote_worker = None
        return ret

    def setup_kind(self, build):
        self._started_kind_deferred = build.render(self.kind)

    @defer.inlineCallbacks
    def get_started_kind(self):
        if self._started_kind_deferred:
            self._started_kind = yield self._started_kind_deferred
            self._started_kind_deferred = None
        defer.returnValue(self._started_kind)

    def patchBot(self, case, remoteMethod, patch):
        case.patch(BotBase, remoteMethod, patch)


class ControllableLatentWorker(AbstractLatentWorker):

    """
    A latent worker that can be controlled by tests.
    """
    builds_may_be_incompatible = True

    def __init__(self, name, controller, **kwargs):
        self._controller = controller
        AbstractLatentWorker.__init__(self, name, None, **kwargs)

    def checkConfig(self, name, _, **kwargs):
        AbstractLatentWorker.checkConfig(
            self, name, None,
            build_wait_timeout=self._controller.build_wait_timeout,
            **kwargs)

    def reconfigService(self, name, _, **kwargs):
        AbstractLatentWorker.reconfigService(
            self, name, None,
            build_wait_timeout=self._controller.build_wait_timeout,
            **kwargs)

    @defer.inlineCallbacks
    def isCompatibleWithBuild(self, build_props):
        if not self._controller.starting and not self._controller.started:
            defer.returnValue(True)

        requested_kind = yield build_props.render((self._controller.kind))
        curr_kind = yield self._controller.get_started_kind()
        defer.returnValue(requested_kind == curr_kind)

    def start_instance(self, build):
        self._controller.setup_kind(build)

        assert not self._controller.stopping

        self._controller.starting = True
        if self._controller.auto_start_flag:
            self._controller.do_start_instance()
            return defer.succeed(True)

        self._controller._start_deferred = defer.Deferred()
        return self._controller._start_deferred

    def stop_instance(self, build):
        assert not self._controller.stopping
        # TODO: we get duplicate stop_instance sometimes, this might indicate
        # a bug in shutdown code path of AbstractWorkerController
        # assert self._controller.started or self._controller.starting:

        self._controller.started = False
        self._controller.starting = False
        self._controller.stopping = True
        if self._controller.auto_stop_flag:
            self._controller.do_stop_instance()
            return defer.succeed(True)
        self._controller._stop_deferred = defer.Deferred()
        return self._controller._stop_deferred
