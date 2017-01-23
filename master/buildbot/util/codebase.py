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


class AbsoluteSourceStampsMixin(object):
    # record changes and revisions per codebase

    _lastCodebases = None

    @defer.inlineCallbacks
    def getCodebaseDict(self, codebase):
        assert self.codebases

        if self._lastCodebases is None:
            self._lastCodebases = yield self.getState('lastCodebases', {})

        # may fail with KeyError
        defer.returnValue(self._lastCodebases.get(codebase, self.codebases[codebase]))

    @defer.inlineCallbacks
    def recordChange(self, change):
        codebase = yield self.getCodebaseDict(change.codebase)
        lastChange = codebase.get('lastChange', -1)

        if change.number > lastChange:
            self._lastCodebases[change.codebase] = {
                'repository': change.repository,
                'branch': change.branch,
                'revision': change.revision,
                'lastChange': change.number
            }
            yield self.setState('lastCodebases', self._lastCodebases)
