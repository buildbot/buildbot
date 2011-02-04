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
from buildbot.db import base

class SourceStampsConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle source stamps in the database
    """

    def createSourceStamp(self, branch, revision, repository, project,
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
