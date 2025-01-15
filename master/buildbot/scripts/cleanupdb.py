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

import os
from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot import config as config_module
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection


async def doCleanupDatabase(config, master_cfg) -> None:
    if not config['quiet']:
        print(f"cleaning database ({master_cfg.db.db_url})")

    master = BuildMaster(config['basedir'])
    master.config = master_cfg
    db = master.db
    try:
        await db.setup(check_version=False, verbose=not config['quiet'])
        res = await db.logs.getLogs()
        percent = 0
        saved = 0
        for i, log in enumerate(res, start=1):
            saved += await db.logs.compressLog(log.id, force=config['force'])
            if not config['quiet'] and percent != int(i * 100 / len(res)):
                percent = int(i * 100 / len(res))
                print(f" {percent}%  {saved} saved", flush=True)
                saved = 0

        assert master.db._engine is not None
        vacuum_stmt = {
            # https://www.postgresql.org/docs/current/sql-vacuum.html
            'postgresql': f'VACUUM FULL {master.db.model.logchunks.name};',
            # https://dev.mysql.com/doc/refman/5.7/en/optimize-table.html
            'mysql': f'OPTIMIZE TABLE {master.db.model.logchunks.name};',
            # https://www.sqlite.org/lang_vacuum.html
            'sqlite': 'vacuum;',
        }.get(master.db._engine.dialect.name)

        if vacuum_stmt is not None:

            def thd(conn: Connection) -> None:
                if not config['quiet']:
                    print(f"executing vacuum operation '{vacuum_stmt}'...", flush=True)

                # vacuum operation cannot be done in a transaction
                # https://github.com/sqlalchemy/sqlalchemy/discussions/6959#discussioncomment-1251681
                with conn.execution_options(isolation_level='AUTOCOMMIT'):
                    conn.exec_driver_sql(vacuum_stmt).close()

                conn.commit()

            await db.pool.do(thd)
    finally:
        await db.pool.stop()


@in_reactor
async def cleanupDatabase(config):  # pragma: no cover
    # we separate the actual implementation to protect unit tests
    # from @in_reactor which stops the reactor
    return defer.Deferred.fromCoroutine(_cleanupDatabase(config))


async def _cleanupDatabase(config) -> int:
    if not base.checkBasedir(config):
        return 1

    config['basedir'] = os.path.abspath(config['basedir'])

    orig_cwd = os.getcwd()

    try:
        os.chdir(config['basedir'])

        with base.captureErrors(
            (SyntaxError, ImportError), f"Unable to load 'buildbot.tac' from '{config['basedir']}':"
        ):
            configFile = base.getConfigFileFromTac(config['basedir'])

        with base.captureErrors(
            config_module.ConfigErrors, f"Unable to load '{configFile}' from '{config['basedir']}':"
        ):
            master_cfg = base.loadConfig(config, configFile)

        if not master_cfg:
            return 1

        await doCleanupDatabase(config, master_cfg)

        if not config['quiet']:
            print("cleanup complete")
    finally:
        os.chdir(orig_cwd)

    return 0
