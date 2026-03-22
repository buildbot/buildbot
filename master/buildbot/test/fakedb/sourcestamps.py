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


class Patch(Row):
    table = "patches"

    id_column = 'id'

    def __init__(
        self,
        id: int | None = None,
        patchlevel: int = 0,
        patch_base64: str = 'aGVsbG8sIHdvcmxk',  # 'hello, world',
        patch_author: str | None = None,
        patch_comment: str | None = None,
        subdir: str | None = None,
    ) -> None:
        super().__init__(
            id=id,
            patchlevel=patchlevel,
            patch_base64=patch_base64,
            patch_author=patch_author,
            patch_comment=patch_comment,
            subdir=subdir,
        )


class NotSet:
    pass


class SourceStamp(Row):
    table = "sourcestamps"

    id_column = 'id'
    hashedColumns = [
        (
            'ss_hash',
            (
                'branch',
                'revision',
                'repository',
                'project',
                'codebase',
                'patchid',
            ),
        )
    ]

    def __init__(
        self,
        id: int | None = None,
        branch: str | None = 'master',
        revision: str | None | type[NotSet] = NotSet,
        patchid: int | None = None,
        repository: str = 'repo',
        codebase: str = '',
        project: str = 'proj',
        created_at: int = 89834834,
        ss_hash: str | None = None,
    ) -> None:
        if revision is NotSet:
            revision = f'rev-{id}'
        super().__init__(
            id=id,
            branch=branch,
            revision=revision,
            patchid=patchid,
            repository=repository,
            codebase=codebase,
            project=project,
            created_at=created_at,
            ss_hash=ss_hash,
        )
