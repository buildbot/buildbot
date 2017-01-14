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

from zope.interface import implementer

from buildbot import pbutil
from buildbot import util
from buildbot.interfaces import IStatusReceiver
from buildbot.util import service


@implementer(IStatusReceiver)
class StatusReceiverBase:

    def requestSubmitted(self, request):
        pass

    def requestCancelled(self, builder, request):
        pass

    def buildsetSubmitted(self, buildset):
        pass

    def builderAdded(self, builderName, builder):
        pass

    def builderChangedState(self, builderName, state):
        pass

    def buildStarted(self, builderName, build):
        pass

    def buildETAUpdate(self, build, ETA):
        pass

    def changeAdded(self, change):
        pass

    def stepStarted(self, build, step):
        pass

    def stepTextChanged(self, build, step, text):
        pass

    def stepText2Changed(self, build, step, text2):
        pass

    def stepETAUpdate(self, build, step, ETA, expectations):
        pass

    def logStarted(self, build, step, log):
        pass

    def logChunk(self, build, step, log, channel, text):
        pass

    def logFinished(self, build, step, log):
        pass

    def stepFinished(self, build, step, results):
        pass

    def buildFinished(self, builderName, build, results):
        pass

    def builderRemoved(self, builderName):
        pass

    def workerConnected(self, workerName):
        pass

    def workerDisconnected(self, workerName):
        pass

    def workerPaused(self, name):
        pass

    def workerUnpaused(self, name):
        pass

    def checkConfig(self, otherStatusReceivers):
        pass


class StatusReceiverMultiService(StatusReceiverBase, service.AsyncMultiService,
                                 util.ComparableMixin):

    def __init__(self):
        service.AsyncMultiService.__init__(self)


class StatusReceiverService(StatusReceiverBase, service.AsyncService,
                            util.ComparableMixin):
    pass


StatusReceiver = StatusReceiverService


@implementer(IStatusReceiver)
class StatusReceiverPerspective(StatusReceiver, pbutil.NewCredPerspective):
    pass
