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

import base64

import sqlalchemy as sa

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.db import base
from buildbot.util import epoch2datetime
from buildbot.util import unicode2bytes


class SsDict(dict):
    pass


class SsList(list):
    pass


class SourceStampsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    @defer.inlineCallbacks
    def findSourceStampId(self, branch=None, revision=None, repository=None,
                          project=None, codebase=None, patch_body=None,
                          patch_level=None, patch_author=None,
                          patch_comment=None, patch_subdir=None,
                          _reactor=reactor):
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
                ins = self.db.model.patches.insert()
                r = conn.execute(ins, dict(
                    patchlevel=patch_level,
                    patch_base64=base64.b64encode(patch_body_bytes),
                    patch_author=patch_author,
                    patch_comment=patch_comment,
                    subdir=patch_subdir))
                patchid = r.inserted_primary_key[0]
            return patchid
        patchid = yield self.db.pool.do(thd)

        ss_hash = self.hashColumns(branch, revision, repository, project,
                                   codebase, patchid)
        sourcestampid = yield self.findSomethingId(
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
                'created_at': _reactor.seconds(),
            })
        defer.returnValue(sourcestampid)

    @base.cached("ssdicts")
    def getSourceStamp(self, ssid):
        def thd(conn):
            tbl = self.db.model.sourcestamps
            q = tbl.select(whereclause=(tbl.c.id == ssid))
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            ssdict = self._rowToSsdict_thd(conn, row)
            res.close()
            return ssdict
        return self.db.pool.do(thd)

    def getSourceStampsForBuild(self, buildid):
        assert buildid > 0

        def thd(conn):
            # Get SourceStamps for the build
            builds_tbl = self.db.model.builds
            reqs_tbl = self.db.model.buildrequests
            bsets_tbl = self.db.model.buildsets
            bsss_tbl = self.db.model.buildset_sourcestamps
            sstamps_tbl = self.db.model.sourcestamps

            from_clause = builds_tbl.join(reqs_tbl,
                                          builds_tbl.c.buildrequestid == reqs_tbl.c.id)
            from_clause = from_clause.join(bsets_tbl,
                                           reqs_tbl.c.buildsetid == bsets_tbl.c.id)
            from_clause = from_clause.join(bsss_tbl,
                                           bsets_tbl.c.id == bsss_tbl.c.buildsetid)
            from_clause = from_clause.join(sstamps_tbl,
                                           bsss_tbl.c.sourcestampid == sstamps_tbl.c.id)

            q = sa.select([sstamps_tbl]).select_from(
                from_clause).where(builds_tbl.c.id == buildid)
            res = conn.execute(q)
            return [self._rowToSsdict_thd(conn, row)
                    for row in res.fetchall()]

        return self.db.pool.do(thd)

    def getSourceStamps(self):
        def thd(conn):
            tbl = self.db.model.sourcestamps
            q = tbl.select()
            res = conn.execute(q)
            return [self._rowToSsdict_thd(conn, row)
                    for row in res.fetchall()]
        return self.db.pool.do(thd)

    def _rowToSsdict_thd(self, conn, row):
        ssid = row.id
        ssdict = SsDict(ssid=ssid, branch=row.branch,
                        revision=row.revision, patchid=None, patch_body=None,
                        patch_level=None, patch_author=None, patch_comment=None,
                        patch_subdir=None, repository=row.repository,
                        codebase=row.codebase, project=row.project,
                        created_at=epoch2datetime(row.created_at))
        patchid = row.patchid

        # fetch the patch, if necessary
        if patchid is not None:
            tbl = self.db.model.patches
            q = tbl.select(whereclause=(tbl.c.id == patchid))
            res = conn.execute(q)
            row = res.fetchone()
            if row:
                # note the subtle renaming here
                ssdict['patchid'] = patchid
                ssdict['patch_level'] = row.patchlevel
                ssdict['patch_subdir'] = row.subdir
                ssdict['patch_author'] = row.patch_author
                ssdict['patch_comment'] = row.patch_comment
                body = base64.b64decode(row.patch_base64)
                ssdict['patch_body'] = body
            else:
                log.msg('patchid %d, referenced from ssid %d, not found'
                        % (patchid, ssid))
            res.close()
        return ssdict
