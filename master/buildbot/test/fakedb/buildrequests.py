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


class BuildRequest(Row):
    table = "buildrequests"

    id_column = 'id'

    def __init__(
        self,
        id=None,
        buildsetid=None,
        builderid=None,
        priority=0,
        complete=0,
        results=-1,
        submitted_at=12345678,
        complete_at=None,
        waited_for=0,
    ):
        super().__init__(
            id=id,
            buildsetid=buildsetid,
            builderid=builderid,
            priority=priority,
            complete=complete,
            results=results,
            submitted_at=submitted_at,
            complete_at=complete_at,
            waited_for=waited_for,
        )


class BuildRequestClaim(Row):
    table = "buildrequest_claims"

    def __init__(self, brid=None, masterid=None, claimed_at=None):
        super().__init__(brid=brid, masterid=masterid, claimed_at=claimed_at)
