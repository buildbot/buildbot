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
        id=None,
        patchlevel=0,
        patch_base64='aGVsbG8sIHdvcmxk',  # 'hello, world',
        patch_author=None,
        patch_comment=None,
        subdir=None,
    ):
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
        id=None,
        branch='master',
        revision=NotSet,
        patchid=None,
        repository='repo',
        codebase='',
        project='proj',
        created_at=89834834,
        ss_hash=None,
    ):
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
