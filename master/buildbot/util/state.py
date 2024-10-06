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


class StateMixin:
    # state management

    _objectid = None

    async def getState(self, *args, **kwargs):
        # get the objectid, if not known
        if self._objectid is None:
            self._objectid = await self.master.db.state.getObjectId(
                self.name, self.__class__.__name__
            )

        rv = await self.master.db.state.getState(self._objectid, *args, **kwargs)
        return rv

    async def setState(self, key, value):
        # get the objectid, if not known
        if self._objectid is None:
            self._objectid = await self.master.db.state.getObjectId(
                self.name, self.__class__.__name__
            )

        await self.master.db.state.setState(self._objectid, key, value)
