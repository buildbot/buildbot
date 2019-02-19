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

import tempfile

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import utils
from twisted.python import log

from zope.interface import implementer

from buildbot import interfaces
from buildbot.util import service
from buildbot.worker.latent import AbstractLatentWorker


@implementer(interfaces.ISuspendableWorker)
class SuspendableWorker(AbstractLatentWorker):

    def checkConfig(name, password, **kwargs):
        AbstractLatentWorker.checkConfig(name, password, **kwargs)

    def reconfigService(self, name, password, **kwargs):
        return AbstractLatentWorker.reconfigService(self, name, password,
                                                    **kwargs)


@implementer(interfaces.ISuspendableMachine)
class SuspendableMachine(service.BuildbotService, object):

    def checkConfig(self, **kwargs):
        pass

    def reconfigService(self, name=None, workernames=None):
        assert self.name == name
        self.workernames = workernames

    def __repr__(self):
        return "<SuspendableMachine '%r' at %d>" % (
            self.name, id(self))
