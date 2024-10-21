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

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.internet import defer
from twisted.python import deprecate
from twisted.python import log
from twisted.python import versions

from buildbot.db import base
from buildbot.util import bytes2unicode
from buildbot.util import epoch2datetime
from buildbot.util import unicode2bytes
from buildbot.util.sautils import hash_columns
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    import datetime


@dataclass
class PatchModel:
    patchid: int
    body: bytes
    level: int
    author: str
    comment: str
    subdir: str | None = None


@dataclass
class SourceStampModel:
    ssid: int
    branch: str | None
    revision: str | None
    repository: str
    created_at: datetime.datetime
    codebase: str = ''
    project: str = ''

    patch: PatchModel | None = None

    # For backward compatibility from when SsDict inherited from Dict
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'SourceStampsConnectorComponent '
                'getSourceStamp, get_sourcestamps_for_buildset, '
                'getSourceStampsForBuild, and getSourceStamps'
                'no longer return SourceStamp as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        # moved to PatchModel object
        patch_key = {
            'patchid': 'patchid',
            'patch_body': 'body',
            'patch_level': 'level',
            'patch_author': 'author',
            'patch_comment': 'comment',
            'patch_subdir': 'subdir',
        }.get(key)
        if patch_key is not None:
            if self.patch is None:
                return None

            return getattr(self.patch, patch_key)

        raise KeyError(key)


@deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), SourceStampModel)
class SsDict(SourceStampModel):
    pass


class SourceStampsConnectorComponent(base.DBConnectorComponent):
    @defer.inlineCallbacks
    def findSourceStampId(
        self,
        branch=None,
        revision=None,
        repository=None,
        project=None,
        codebase=None,
        patch_body=None,
        patch_level=None,
        patch_author=None,
        patch_comment=None,
        patch_subdir=None,
    ):
        sourcestampid, _ = yield self.findOrCreateId(
            branch,
            revision,
            repository,
            project,
            codebase,
            patch_body,
            patch_level,
            patch_author,
            patch_comment,
            patch_subdir,
        )
        return sourcestampid

    @defer.inlineCallbacks
    def findOrCreateId(
        self,
        branch=None,
        revision=None,
        repository=None,
        project=None,
        codebase=None,
        patch_body=None,
        patch_level=None,
        patch_author=None,
        patch_comment=None,
        patch_subdir=None,
    ):
        tbl = self.db.model.sourcestamps

        assert codebase is not None, "codebase cannot be None"
        assert project is not None, "project cannot be None"
        assert repository is not None, "repository cannot be None"
        self.checkLength(tbl.c.branch, branch)
        self.checkLength(tbl.c.revision, revision)
        self.checkLength(tbl.c.repository, repository)
        self.checkLength(tbl.c.project, project)

        # get a patchid, if we have a patch
        def thd(conn):
            patchid = None
            if patch_body:
                patch_body_bytes = unicode2bytes(patch_body)
                patch_base64_bytes = base64.b64encode(patch_body_bytes)
                ins = self.db.model.patches.insert()
                r = conn.execute(
                    ins,
                    {
                        "patchlevel": patch_level,
                        "patch_base64": bytes2unicode(patch_base64_bytes),
                        "patch_author": patch_author,
                        "patch_comment": patch_comment,
                        "subdir": patch_subdir,
                    },
                )
                conn.commit()
                patchid = r.inserted_primary_key[0]
            return patchid

        patchid = yield self.db.pool.do(thd)

        ss_hash = hash_columns(branch, revision, repository, project, codebase, patchid)
        sourcestampid, found = yield self.findOrCreateSomethingId(
            tbl=tbl,
            whereclause=tbl.c.ss_hash == ss_hash,
            insert_values={
                'branch': branch,
                'revision': revision,
                'repository': repository,
                'codebase': codebase,
                'project': project,
                'patchid': patchid,
                'ss_hash': ss_hash,
                'created_at': int(self.master.reactor.seconds()),
            },
        )
        return sourcestampid, found

    # returns a Deferred that returns a value
    @base.cached("ssdicts")
    def getSourceStamp(self, ssid) -> defer.Deferred[SourceStampModel | None]:
        def thd(conn) -> SourceStampModel | None:
            tbl = self.db.model.sourcestamps
            q = tbl.select().where(tbl.c.id == ssid)
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            model = self._rowToModel_thd(conn, row)
            res.close()
            return model

        return self.db.pool.do(thd)

    # returns a Deferred that returns a value
    def get_sourcestamps_for_buildset(self, buildsetid) -> defer.Deferred[list[SourceStampModel]]:
        def thd(conn) -> list[SourceStampModel]:
            bsets_tbl = self.db.model.buildsets
            bsss_tbl = self.db.model.buildset_sourcestamps
            sstamps_tbl = self.db.model.sourcestamps

            from_clause = bsets_tbl.join(bsss_tbl, bsets_tbl.c.id == bsss_tbl.c.buildsetid).join(
                sstamps_tbl, bsss_tbl.c.sourcestampid == sstamps_tbl.c.id
            )

            q = sa.select(sstamps_tbl).select_from(from_clause).where(bsets_tbl.c.id == buildsetid)

            res = conn.execute(q)
            return [self._rowToModel_thd(conn, row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    # returns a Deferred that returns a value
    def getSourceStampsForBuild(self, buildid) -> defer.Deferred[list[SourceStampModel]]:
        assert buildid > 0

        def thd(conn) -> list[SourceStampModel]:
            # Get SourceStamps for the build
            builds_tbl = self.db.model.builds
            reqs_tbl = self.db.model.buildrequests
            bsets_tbl = self.db.model.buildsets
            bsss_tbl = self.db.model.buildset_sourcestamps
            sstamps_tbl = self.db.model.sourcestamps

            from_clause = builds_tbl.join(reqs_tbl, builds_tbl.c.buildrequestid == reqs_tbl.c.id)
            from_clause = from_clause.join(bsets_tbl, reqs_tbl.c.buildsetid == bsets_tbl.c.id)
            from_clause = from_clause.join(bsss_tbl, bsets_tbl.c.id == bsss_tbl.c.buildsetid)
            from_clause = from_clause.join(
                sstamps_tbl, bsss_tbl.c.sourcestampid == sstamps_tbl.c.id
            )

            q = sa.select(sstamps_tbl).select_from(from_clause).where(builds_tbl.c.id == buildid)
            res = conn.execute(q)
            return [self._rowToModel_thd(conn, row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    # returns a Deferred that returns a value
    def getSourceStamps(self) -> defer.Deferred[list[SourceStampModel]]:
        def thd(conn) -> list[SourceStampModel]:
            tbl = self.db.model.sourcestamps
            q = tbl.select()
            res = conn.execute(q)
            return [self._rowToModel_thd(conn, row) for row in res.fetchall()]

        return self.db.pool.do(thd)

    def _rowToModel_thd(self, conn, row) -> SourceStampModel:
        ssid = row.id
        model = SourceStampModel(
            ssid=ssid,
            branch=row.branch,
            revision=row.revision,
            repository=row.repository,
            codebase=row.codebase,
            project=row.project,
            created_at=epoch2datetime(row.created_at),
        )
        patchid = row.patchid

        # fetch the patch, if necessary
        if patchid is not None:
            tbl = self.db.model.patches
            q = tbl.select().where(tbl.c.id == patchid)
            res = conn.execute(q)
            row = res.fetchone()
            if row:
                model.patch = PatchModel(
                    patchid=patchid,
                    body=base64.b64decode(row.patch_base64),
                    level=row.patchlevel,
                    author=row.patch_author,
                    comment=row.patch_comment,
                    subdir=row.subdir,
                )
            else:
                log.msg(f'patchid {patchid}, referenced from ssid {ssid}, not found')
            res.close()
        return model
