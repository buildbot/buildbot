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
from __future__ import division
from __future__ import print_function

import os
import sys

from twisted.internet import defer

from buildbot import config as config_module
from buildbot import monkeypatches
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor


@defer.inlineCallbacks
def doCleanupDatabase(config, master_cfg):
    if not config['quiet']:
        print("cleaning database (%s)" % (master_cfg.db['db_url']))

    master = BuildMaster(config['basedir'])
    master.config = master_cfg
    db = master.db
    yield db.setup(check_version=False, verbose=not config['quiet'])
    res = yield db.logs.getLogs()
    i = 0
    percent = 0
    saved = 0
    for log in res:
        saved += yield db.logs.compressLog(log['id'], force=config['force'])
        i += 1
        if not config['quiet'] and percent != i * 100 / len(res):
            percent = i * 100 / len(res)
            print(" {0}%  {1} saved".format(percent, saved))
            saved = 0
            sys.stdout.flush()

    if master_cfg.db['db_url'].startswith("sqlite"):
        if not config['quiet']:
            print("executing sqlite vacuum function...")

        # sqlite vacuum function rebuild the whole database to claim
        # free disk space back
        def thd(engine):
            # In Python 3.6 and higher, sqlite3 no longer commits an
            # open transaction before DDL statements.
            # It is necessary to set the isolation_level to none
            # for auto-commit mode before doing a VACUUM.
            # See: https://bugs.python.org/issue28518

            # Get the underlying sqlite connection from SQLAlchemy.
            sqlite_conn = engine.connection.connection
            # Set isolation_level to 'auto-commit mode'
            sqlite_conn.isolation_level = None
            sqlite_conn.execute("vacuum;").close()

        yield db.pool.do(thd)


@in_reactor
def cleanupDatabase(config, _noMonkey=False):  # pragma: no cover
    # we separate the actual implementation to protect unit tests
    # from @in_reactor which stops the reactor
    if not _noMonkey:
        monkeypatches.patch_all()
    return _cleanupDatabase(config, _noMonkey=False)


@defer.inlineCallbacks
def _cleanupDatabase(config, _noMonkey=False):

    if not base.checkBasedir(config):
        defer.returnValue(1)
        return

    config['basedir'] = os.path.abspath(config['basedir'])
    os.chdir(config['basedir'])

    with base.captureErrors((SyntaxError, ImportError),
                            "Unable to load 'buildbot.tac' from '%s':" % (config['basedir'],)):
        configFile = base.getConfigFileFromTac(config['basedir'])

    with base.captureErrors(config_module.ConfigErrors,
                            "Unable to load '%s' from '%s':" % (configFile, config['basedir'])):
        master_cfg = base.loadConfig(config, configFile)

    if not master_cfg:
        defer.returnValue(1)
        return

    yield doCleanupDatabase(config, master_cfg)

    if not config['quiet']:
        print("cleanup complete")

    defer.returnValue(0)
