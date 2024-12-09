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

from __future__ import annotations

from buildbot.test.fakedb.row import Row


class Buildset(Row):
    table = "buildsets"

    id_column = 'id'

    def __init__(
        self,
        id=None,
        external_idstring='extid',
        reason='because',
        submitted_at=12345678,
        complete=0,
        complete_at=None,
        results=-1,
        rebuilt_buildid=None,
        parent_buildid=None,
        parent_relationship=None,
    ):
        super().__init__(
            id=id,
            external_idstring=external_idstring,
            reason=reason,
            submitted_at=submitted_at,
            complete=complete,
            complete_at=complete_at,
            results=results,
            rebuilt_buildid=rebuilt_buildid,
            parent_buildid=parent_buildid,
            parent_relationship=parent_relationship,
        )


class BuildsetProperty(Row):
    table = "buildset_properties"

    def __init__(self, buildsetid=None, property_name='prop', property_value='[22, "fakedb"]'):
        super().__init__(
            buildsetid=buildsetid, property_name=property_name, property_value=property_value
        )


class BuildsetSourceStamp(Row):
    table = "buildset_sourcestamps"

    id_column = 'id'

    def __init__(self, id=None, buildsetid=None, sourcestampid=None):
        super().__init__(id=id, buildsetid=buildsetid, sourcestampid=sourcestampid)
