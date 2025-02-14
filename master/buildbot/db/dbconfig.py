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


from contextlib import contextmanager

from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import ProgrammingError

from buildbot.config.master import DBConfig as MasterDBConfig
from buildbot.config.master import MasterConfig
from buildbot.db import enginestrategy
from buildbot.db import model
from buildbot.db import state


class FakeDBConnector:
    def __init__(self, engine):
        self.pool = FakePool(engine)
        self.master = FakeMaster()
        self.model = model.Model(self)
        self.state = state.StateConnectorComponent(self)

    @contextmanager
    def connect(self):
        try:
            with self.pool.engine.connect() as conn:
                yield conn
        finally:
            self.pool.engine.dispose()


class FakeCacheManager:
    def get_cache(self, cache_name, miss_fn):
        return None


class FakeMaster:
    def __init__(self):
        self.caches = FakeCacheManager()


class FakePool:
    def __init__(self, engine):
        self.engine = engine


class DbConfig:
    db_config: MasterDBConfig

    def __init__(self, BuildmasterConfig, basedir, name="config"):
        self.db_config = MasterConfig.get_dbconfig_from_config(BuildmasterConfig, throwErrors=False)
        self.basedir = basedir
        self.name = name

    def getDb(self):
        try:
            db = FakeDBConnector(
                engine=enginestrategy.create_engine(self.db_config.db_url, basedir=self.basedir)
            )
        except Exception:
            # db_config.db_url is probably trash. Just ignore, config.py db part will
            # create proper message
            return None

        with db.connect() as conn:
            try:
                self.objectid = db.state.thdGetObjectId(conn, self.name, "DbConfig")['id']
            except (ProgrammingError, OperationalError):
                conn.rollback()
                # ProgrammingError: mysql&pg, OperationalError: sqlite
                # assume db is not initialized
                return None

        return db

    def get(self, name, default=state.StateConnectorComponent.Thunk):
        db = self.getDb()
        if db is not None:
            with db.connect() as conn:
                ret = db.state.thdGetState(conn, self.objectid, name, default=default)
        else:
            if default is not state.StateConnectorComponent.Thunk:
                return default
            raise KeyError("Db not yet initialized")
        return ret

    def set(self, name, value):
        db = self.getDb()
        if db is not None:
            with db.connect() as conn:
                db.state.thdSetState(conn, self.objectid, name, value)
