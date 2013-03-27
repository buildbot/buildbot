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

import sqlalchemy as sa
from twisted.internet import reactor
from buildbot.util import epoch2datetime
from buildbot.db import base

class AlreadySetupError(Exception):
    pass

class MasterConfigDict(dict):
    pass

class MastersConfigConnectorComponent(base.DBConnectorComponent):

    def setupMaster(self, buildbotURL, _master_objectid=None):
        def thd(conn):
            tbl = self.db.model.mastersconfig

            def update():
                q = tbl.update(whereclause=(tbl.c.objectid == _master_objectid))
                res = conn.execute(q, buildbotURL=buildbotURL)
                return res.rowcount > 0

            def insert():
                res = conn.execute(tbl.insert(),
                                   buildbotURL=buildbotURL,
                                   objectid=_master_objectid)

            if update():
                return
            
            try:
                insert()                
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                raise AlreadySetupError
            
        return self.db.pool.do(thd)         
           
    @base.cached('masterURLdict')
    def getMasterURL(self, brid=None):
        def thd(conn):
            if (brid) is not None:
                mast_tbl=self.db.model.mastersconfig
                claims_tbl = self.db.model.buildrequest_claims
                res = conn.execute(sa.select(columns=[mast_tbl], from_obj=[
                claims_tbl.join(mast_tbl,
                                   (claims_tbl.c.objectid == mast_tbl.c.objectid)) ],
                                             distinct=True,
                                             whereclause=(claims_tbl.c.brid == brid)))
                row = res.fetchone()
                masterconfigdict = None
                if row:
                    masterconfigdict = self._masterconfigdictFromRow(row)
                res.close()
                return masterconfigdict
            
        return self.db.pool.do(thd)

    def _masterconfigdictFromRow(self, row):
        return MasterConfigDict(id=row.id, buildbotURL=row.buildbotURL, objectid=row.objectid)