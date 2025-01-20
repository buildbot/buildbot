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


class Codebase(Row):
    table = "codebases"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(
        self,
        *,
        id: int | None = None,
        projectid: int | None = None,
        name: str = 'fake_codebase',
        name_hash: str | None = None,
        slug: str | None = None,
    ) -> None:
        if slug is None:
            slug = name
        super().__init__(
            id=id,
            projectid=projectid,
            name=name,
            name_hash=name_hash,
            slug=slug,
        )


class CodebaseCommit(Row):
    table = "codebase_commits"

    id_column = 'id'

    def __init__(
        self,
        *,
        id: int,
        codebaseid: int,
        author: str = 'author1',
        committer: str | None = 'committer1',
        comments: str = 'comments1',
        when_timestamp: int = 1234567,
        revision: str | None = None,
        parent_commitid: int | None = None,
    ):
        if revision is None:
            revision = f'rev{id}'
        super().__init__(
            id=id,
            codebaseid=codebaseid,
            author=author,
            committer=committer,
            comments=comments,
            when_timestamp=when_timestamp,
            revision=revision,
            parent_commitid=parent_commitid,
        )


class CodebaseBranch(Row):
    table = "codebase_branches"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(
        self,
        *,
        id: int | None = None,
        codebaseid: int | None = None,
        name: str = 'fake_branch',
        name_hash: str | None = None,
        commitid: int | None = None,
        last_timestamp: int = 1234567,
    ):
        super().__init__(
            id=id,
            codebaseid=codebaseid,
            name=name,
            name_hash=name_hash,
            commitid=commitid,
            last_timestamp=last_timestamp,
        )
