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

from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import ProgrammingError

from buildbot.config import MasterConfig
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
        self.db_url = MasterConfig.getDbUrlFromConfig(
            BuildmasterConfig, throwErrors=False)
        self.basedir = basedir
        self.name = name

    def getDb(self):
        try:
            db_engine = enginestrategy.create_engine(self.db_url,
                                                     basedir=self.basedir)
        except Exception:
            # db_url is probably trash. Just ignore, config.py db part will
            # create proper message
            return None
        db = FakeDBConnector()
        db.master = FakeMaster()
        db.pool = FakePool()
        db.pool.engine = db_engine
        db.master.caches = FakeCacheManager()
        db.model = model.Model(db)
        db.state = state.StateConnectorComponent(db)
        try:
            self.objectid = db.state.thdGetObjectId(
                db_engine, self.name, "DbConfig")['id']
        except (ProgrammingError, OperationalError):
            # ProgrammingError: mysql&pg, OperationalError: sqlite
            # assume db is not initialized
            db.pool.engine.close()
            return None
        return db

    def get(self, name, default=state.StateConnectorComponent.Thunk):
        db = self.getDb()
        if db is not None:
            ret = db.state.thdGetState(
                db.pool.engine, self.objectid, name, default=default)
            db.pool.engine.close()
        else:
            if default is not state.StateConnectorComponent.Thunk:
                return default
            raise KeyError("Db not yet initialized")
        return ret

    def set(self, name, value):
        db = self.getDb()
        if db is not None:
            db.state.thdSetState(db.pool.engine, self.objectid, name, value)
            db.pool.engine.close()
