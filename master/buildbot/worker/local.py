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
# Portions Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function

import os

from twisted.internet import defer

from buildbot.config import error
from buildbot.worker.base import Worker


class LocalWorker(Worker):

    def checkConfig(self, name, workdir=None, usePty=False, **kwargs):
        Worker.checkConfig(self, name, None, **kwargs)
        self.LocalWorkerFactory = None
        try:
            # importing here to avoid dependency on buildbot worker package
            from buildbot_worker.bot import LocalWorker as RemoteLocalWorker
            self.LocalWorkerFactory = RemoteLocalWorker
        except ImportError:
            error("LocalWorker needs the buildbot-worker package installed "
                  "(pip install buildbot-worker)")
        self.remote_worker = None

    @defer.inlineCallbacks
    def reconfigService(self, name, workdir=None, usePty=False, **kwargs):
        Worker.reconfigService(self, name, None, **kwargs)
        if workdir is None:
            workdir = name
        workdir = os.path.abspath(
            os.path.join(self.master.basedir, "workers", workdir))
        if not os.path.isdir(workdir):
            os.makedirs(workdir)

        if self.remote_worker is None:
            # create the actual worker as a child service
            # we only create at reconfig, to avoid polluting memory in case of
            # reconfig
            self.remote_worker = self.LocalWorkerFactory(name, workdir, usePty)
            yield self.remote_worker.setServiceParent(self)
        else:
            # The case of a reconfig, we forward the parameters
            self.remote_worker.bot.basedir = workdir
            self.remote_worker.usePty = usePty
