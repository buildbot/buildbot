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

"""
Support for creating and reading source stamps
"""

import base64
from twisted.python import log
from buildbot.db import base

class SsDict(dict):
    pass

class SourceStampsConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle source stamps in the database
    """

    def addSourceStamp(self, branch, revision, repository, project,
                          patch_body=None, patch_level=0, patch_subdir=None,
                          changeids=[]):
        """
        Create a new SourceStamp instance with the given attributes, and return
        its sourcestamp ID, via a Deferred.
        """
        def thd(conn):
            # handle inserting a patch
            patchid = None
            if patch_body is not None:
                ins = self.db.model.patches.insert()
                r = conn.execute(ins, dict(
                    patchlevel=patch_level,
                    patch_base64=base64.b64encode(patch_body),
                    subdir=patch_subdir))
                patchid = r.inserted_primary_key[0]

            # insert the sourcestamp itself
            ins = self.db.model.sourcestamps.insert()
            r = conn.execute(ins, dict(
                branch=branch,
                revision=revision,
                patchid=patchid,
                repository=repository,
                project=project))
            ssid = r.inserted_primary_key[0]

            # handle inserting change ids
            if changeids:
                ins = self.db.model.sourcestamp_changes.insert()
                conn.execute(ins, [
                    dict(sourcestampid=ssid, changeid=changeid)
                    for changeid in changeids ])

            # and return the new ssid
            return ssid
        return self.db.pool.do(thd)

    @base.cached("ssdicts")
    def getSourceStamp(self, ssid):
        """
        Get a dictionary representing the given source stamp, or None if no
        such source stamp exists.

        The dictionary has keys C{ssid}, C{branch}, C{revision}, C{patch_body},
        C{patch_level}, C{patch_subdir}, C{repository}, C{project}, and
        C{changeids}.  Most are simple strings.  The C{changeids} key contains
        a set of change IDs.  The C{patch_*} arguments will be C{None} if no
        patch is attached.  The last is a set of changeids for this source
        stamp.

        @param bsid: buildset ID

        @param no_cache: bypass cache and always fetch from database
        @type no_cache: boolean

        @returns: dictionary as above, or None, via Deferred
        """
        def thd(conn):
            tbl = self.db.model.sourcestamps
            q = tbl.select(whereclause=(tbl.c.id == ssid))
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            ssdict = SsDict(ssid=ssid, branch=row.branch,
                    revision=row.revision, patch_body=None, patch_level=None,
                    patch_subdir=None, repository=row.repository,
                    project=row.project, changeids=set([]))
            patchid = row.patchid
            res.close()

            # fetch the patch, if necessary
            if patchid is not None:
                tbl = self.db.model.patches
                q = tbl.select(whereclause=(tbl.c.id == patchid))
                res = conn.execute(q)
                row = res.fetchone()
                if row:
                    # note the subtle renaming here
                    ssdict['patch_level'] = row.patchlevel
                    ssdict['patch_subdir'] = row.subdir
                    body = base64.b64decode(row.patch_base64)
                    ssdict['patch_body'] = body
                else:
                    log.msg('patchid %d, referenced from ssid %d, not found'
                            % (patchid, ssid))
                res.close()

            # fetch change ids
            tbl = self.db.model.sourcestamp_changes
            q = tbl.select(whereclause=(tbl.c.sourcestampid == ssid))
            res = conn.execute(q)
            for row in res:
                ssdict['changeids'].add(row.changeid)
            res.close()

            return ssdict
        return self.db.pool.do(thd)
