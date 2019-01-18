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

import copy

from twisted.internet import defer


class CompatibleLatentWorkerMixin:

    builds_may_be_incompatible = True
    _actual_build_props = None

    def renderWorkerProps(self, build):
        # Deriving classes should implement this method to render and return
        # a Deferred that will have all properties that are needed to start a
        # worker as its result. The Deferred should result in data that can
        # be copied via copy.deepcopy
        #
        # During actual startup, renderWorkerPropsOnStart should be called
        # which will invoke renderWorkerProps, store a copy of the results for
        # later comparison and return them.
        raise NotImplementedError()

    @defer.inlineCallbacks
    def renderWorkerPropsOnStart(self, build):
        props = yield self.renderWorkerProps(build)
        self._actual_build_props = copy.deepcopy(props)
        defer.returnValue(props)

    @defer.inlineCallbacks
    def isCompatibleWithBuild(self, build):
        if self._actual_build_props is None:
            defer.returnValue(True)

        requested_props = yield self.renderWorkerProps(build)

        defer.returnValue(requested_props == self._actual_build_props)
