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

from buildbot.db import base

class SourceStampSetsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def addSourceStampSet(self):
        def thd(conn):
            # insert the sourcestampset.  sourcestampset has no attributes, but
            # inserting a new row results in a new setid
            r = conn.execute(self.db.model.sourcestampsets.insert(), dict())
            sourcestampsetid = r.inserted_primary_key[0]

            return sourcestampsetid
        return self.db.pool.do(thd)
