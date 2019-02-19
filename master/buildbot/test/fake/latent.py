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


import enum

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial.unittest import SkipTest

from buildbot.test.fake.worker import SeverWorkerConnectionMixin
from buildbot.worker import AbstractLatentWorker

try:
    from buildbot_worker.bot import LocalWorker as RemoteWorker
    from buildbot_worker.base import BotBase
except ImportError:
    RemoteWorker = None


class States(enum.Enum):
    STOPPED = 0
    STARTING = 1
    STARTED = 2
    STOPPING = 3


class LatentController(SeverWorkerConnectionMixin):

    """
    A controller for ``ControllableLatentWorker``.

    https://glyph.twistedmatrix.com/2015/05/separate-your-fakes-and-your-inspectors.html

    Note that by default workers will connect automatically if True is passed
    to start_instance().

    Also by default workers will disconnect automatically just as
    stop_instance() is executed.
    """

    def __init__(self, case, name, kind=None, build_wait_timeout=600, **kwargs):
        self.case = case
        self.build_wait_timeout = build_wait_timeout
        self.worker = ControllableLatentWorker(name, self, **kwargs)
        self.remote_worker = None

        self.state = States.STOPPED
        self.auto_stop_flag = False
        self.auto_start_flag = False
        self.auto_connect_worker = True
        self.auto_disconnect_worker = True

        self.kind = kind
        self._started_kind = None
        self._started_kind_deferred = None

    @property
    def starting(self):
        return self.state == States.STARTING

    @property
    def started(self):
        return self.state == States.STARTED

    @property
    def stopping(self):
        return self.state == States.STOPPING

    @property
    def stopped(self):
        return self.state == States.STOPPED

    def auto_start(self, result):
        self.auto_start_flag = result
        if self.auto_start_flag and self.state == States.STARTING:
            self.start_instance(True)

    def start_instance(self, result):
        self.do_start_instance(result)
        d, self._start_deferred = self._start_deferred, None
        d.callback(result)

    def do_start_instance(self, result):
        assert self.state == States.STARTING
        self.state = States.STARTED
        if self.auto_connect_worker and result is True:
            self.connect_worker()

    @defer.inlineCallbacks
    def auto_stop(self, result):
        self.auto_stop_flag = result
        if self.auto_stop_flag and self.state == States.STOPPING:
            yield self.stop_instance(True)

    @defer.inlineCallbacks
    def stop_instance(self, result):
        yield self.do_stop_instance()
        d, self._stop_deferred = self._stop_deferred, None
        d.callback(result)

    @defer.inlineCallbacks
    def do_stop_instance(self):
        assert self.state == States.STOPPING
        self.state = States.STOPPED
        self._started_kind = None
        if self.auto_disconnect_worker:
            yield self.disconnect_worker()

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
        super().disconnect_worker()
        if self.remote_worker is None:
            return
        self.worker.conn, conn = None, self.worker.conn
        self.remote_worker, worker = None, self.remote_worker

        # LocalWorker does actually disconnect, so we must force disconnection
        # via detached. Note that the worker may have already detached
        if conn is not None:
            conn.loseConnection()
        return worker.disownServiceParent()

    def setup_kind(self, build):
        if build:
            self._started_kind_deferred = build.render(self.kind)
        else:
            self._started_kind_deferred = self.kind

    @defer.inlineCallbacks
    def get_started_kind(self):
        if self._started_kind_deferred:
            self._started_kind = yield self._started_kind_deferred
            self._started_kind_deferred = None
        return self._started_kind

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
        if self._controller.state == States.STOPPED:
            return True

        requested_kind = yield build_props.render((self._controller.kind))
        curr_kind = yield self._controller.get_started_kind()
        return requested_kind == curr_kind

    def start_instance(self, build):
        self._controller.setup_kind(build)

        assert self._controller.state == States.STOPPED
        self._controller.state = States.STARTING

        if self._controller.auto_start_flag:
            self._controller.do_start_instance(True)
            return defer.succeed(True)

        self._controller._start_deferred = defer.Deferred()
        return self._controller._start_deferred

    @defer.inlineCallbacks
    def stop_instance(self, build):
        assert self._controller.state in [States.STARTED, States.STARTING]
        # if we did not succeed starting, at least call back the failure result
        if self._controller.state == States.STARTING:
            self._controller.state = States.STOPPED
            d, self._controller._start_deferred = self._controller._start_deferred, None
            d.callback(False)
        self._controller.state = States.STOPPING

        if self._controller.auto_stop_flag:
            yield self._controller.do_stop_instance()
            return True
        self._controller._stop_deferred = defer.Deferred()
        return (yield self._controller._stop_deferred)
