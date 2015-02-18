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

from buildbot.db import enginestrategy
from buildbot.db import model
from buildbot.db import state


class FakeDBConnector(object):
    pass


class FakeCacheManager(object):

    def get_cache(self, cache_name, miss_fn):
        return None


class FakeMaster(object):
    pass


class FakePool(object):
    pass


class DbConfig(object):

    def __init__(self, BuildmasterConfig, basedir, name="config"):
        if 'db' in BuildmasterConfig:
            self.db_url = BuildmasterConfig['db']['db_url']
        elif 'db_url' in BuildmasterConfig:
            self.db_url = BuildmasterConfig['db_url']
        else:
            self.db_url = 'sqlite:///state.sqlite'
        self.basedir = basedir
        self.name = name

    def getDb(self):
        db_engine = enginestrategy.create_engine(self.db_url,
                                                 basedir=self.basedir)
        db = FakeDBConnector()
        db.master = FakeMaster()
        db.pool = FakePool()
        db.pool.engine = db_engine
        db.master.caches = FakeCacheManager()
        db.model = model.Model(db)
        db.state = state.StateConnectorComponent(db)
        self.objectid = db.state.thdGetObjectId(db_engine, self.name, "DbConfig")['id']
        return db

    def get(self, name, default=state.StateConnectorComponent.Thunk):
        db = self.getDb()
        ret = db.state.thdGetState(db.pool.engine, self.objectid, name, default=default)
        db.pool.engine.close()
        return ret

    def set(self, name, value):
        db = self.getDb()
        db.state.thdSetState(db.pool.engine, self.objectid, name, value)
        db.pool.engine.close()
