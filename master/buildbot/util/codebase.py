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


class AbsoluteSourceStampsMixin:
    # record changes and revisions per codebase

    _lastCodebases = None

    async def getCodebaseDict(self, codebase):
        assert self.codebases

        if self._lastCodebases is None:
            self._lastCodebases = await self.getState('lastCodebases', {})

        # may fail with KeyError
        return self._lastCodebases.get(codebase, self.codebases[codebase])

    async def recordChange(self, change):
        codebase = await self.getCodebaseDict(change.codebase)
        lastChange = codebase.get('lastChange', -1)

        if change.number > lastChange:
            self._lastCodebases[change.codebase] = {
                'repository': change.repository,
                'branch': change.branch,
                'revision': change.revision,
                'lastChange': change.number,
            }
            await self.setState('lastCodebases', self._lastCodebases)
