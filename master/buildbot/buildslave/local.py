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

import os

from buildbot.buildslave.base import BuildSlave
from buildbot.config import error
from twisted.internet import defer


class LocalBuildSlave(BuildSlave):

    def checkConfig(self, name, workdir=None, usePty=False, **kwargs):
        BuildSlave.checkConfig(self, name, None, **kwargs)
        self.LocalBuildSlaveFactory = None
        try:
            # importing here to avoid dependency on buildbot slave package
            from buildslave.bot import LocalBuildSlave as RemoteLocalBuildSlave
            self.LocalBuildSlaveFactory = RemoteLocalBuildSlave
        except ImportError:
            error("LocalBuildSlave needs the buildbot-slave package installed (pip install buildbot-slave)")
        self.remote_slave = None

    @defer.inlineCallbacks
    def reconfigService(self, name, workdir=None, usePty=False, **kwargs):
        BuildSlave.reconfigService(self, name, None, **kwargs)
        if workdir is None:
            workdir = name
        workdir = os.path.abspath(os.path.join(self.master.basedir, "slaves", workdir))
        if not os.path.isdir(workdir):
            os.makedirs(workdir)

        if self.remote_slave is None:
            # create the actual slave as a child service
            # we only create at reconfig, to avoid poluting memory in case of reconfig
            self.remote_slave = self.LocalBuildSlaveFactory(name, workdir, usePty)
            yield self.remote_slave.setServiceParent(self)
        else:
            # The case of a reconfig, we forward the parameters
            self.remote_slave.bot.basedir = workdir
            self.remote_slave.usePty = usePty
