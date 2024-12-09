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


class Change(Row):
    table = "changes"

    id_column = 'changeid'

    def __init__(
        self,
        changeid=None,
        author='frank',
        committer='steve',
        comments='test change',
        branch='master',
        revision='abcd',
        revlink='http://vc/abcd',
        when_timestamp=1200000,
        category='cat',
        repository='repo',
        codebase='',
        project='proj',
        sourcestampid=92,
        parent_changeids=None,
    ):
        super().__init__(
            changeid=changeid,
            author=author,
            committer=committer,
            comments=comments,
            branch=branch,
            revision=revision,
            revlink=revlink,
            when_timestamp=when_timestamp,
            category=category,
            repository=repository,
            codebase=codebase,
            project=project,
            sourcestampid=sourcestampid,
            parent_changeids=parent_changeids,
        )


class ChangeFile(Row):
    table = "change_files"

    def __init__(self, changeid=None, filename=None):
        super().__init__(changeid=changeid, filename=filename)


class ChangeProperty(Row):
    table = "change_properties"

    def __init__(self, changeid=None, property_name=None, property_value=None):
        super().__init__(
            changeid=changeid, property_name=property_name, property_value=property_value
        )


class ChangeUser(Row):
    table = "change_users"

    def __init__(self, changeid=None, uid=None):
        super().__init__(changeid=changeid, uid=uid)
