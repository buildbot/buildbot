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

import sqlalchemy as sa
import sqlalchemy.sql.functions as safunc
from twisted.internet import defer

from buildbot import config as config_module
from buildbot import monkeypatches
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor


@defer.inlineCallbacks
def deleteOldBuilds(db, config):
    m = db.model

    def thd(conn):
        with conn.begin():
            # Delete soucestamps older than --max-days
            # The starting point is not "now" but the most recent sourcestamp..
            max_created_at = conn.execute(
                sa.select([safunc.max(m.sourcestamps.c.created_at)])).scalar()
            if max_created_at is None:
                max_created_at = 0
            max_created_at -= config['max-days'] * 24 * 60 * 60

            res = conn.execute(m.sourcestamps.delete().where(
                m.sourcestamps.c.created_at < max_created_at))

            print('Deleted %s sourcestamps' % res.rowcount)

            conn.execute(m.patches.delete().where(
                m.patches.c.id.notin_(sa.select([m.sourcestamps.c.patchid]))))

            # Delete changes with no link to a sourcestamp.
            conn.execute(m.changes.delete().where(
                m.changes.c.sourcestampid.notin_(sa.select([m.sourcestamps.c.id]))))

            conn.execute(m.changes.update().where(
                m.changes.c.parent_changeids.notin_(
                    sa.select([m.changes.c.changeid]))).values(
                        parent_changeids=None))

            conn.execute(m.change_files.delete().where(
                m.change_files.c.changeid.notin_(sa.select([m.changes.c.changeid]))))

            conn.execute(m.change_properties.delete().where(
                m.change_properties.c.changeid.notin_(sa.select([m.changes.c.changeid]))))

            conn.execute(m.change_users.delete().where(
                m.change_users.c.changeid.notin_(sa.select([m.changes.c.changeid]))))

            conn.execute(m.scheduler_changes.delete().where(
                m.scheduler_changes.c.changeid.notin_(sa.select([m.changes.c.changeid]))))

            # Delete buildsets that have no link to a sourcestamp.
            conn.execute(m.buildset_sourcestamps.delete().where(
                m.buildset_sourcestamps.c.sourcestampid.notin_(
                    sa.select([m.sourcestamps.c.id]))))

            conn.execute(m.buildsets.delete().where(
                m.buildsets.c.id.notin_(
                    sa.select([m.buildset_sourcestamps.c.buildsetid]))))

            conn.execute(m.buildset_properties.delete().where(
                m.buildset_properties.c.buildsetid.notin_(
                    sa.select([m.buildsets.c.id]))))

            conn.execute(m.buildrequests.delete().where(
                m.buildrequests.c.buildsetid.notin_(sa.select([m.buildsets.c.id]))))

            conn.execute(m.buildrequest_claims.delete().where(
                m.buildrequest_claims.c.brid.notin_(sa.select([m.buildrequests.c.id]))))

            conn.execute(m.builds.delete().where(
                m.builds.c.buildrequestid.notin_(sa.select([m.buildrequests.c.id]))))

            conn.execute(m.buildsets.update().where(
                m.buildsets.c.parent_buildid.notin_(
                    sa.select([m.builds.c.id]))).values(
                        parent_buildid=None, parent_relationship=None))

            conn.execute(m.build_properties.delete().where(
                m.build_properties.c.buildid.notin_(sa.select([m.builds.c.id]))))

            conn.execute(m.steps.delete().where(
                m.steps.c.buildid.notin_(sa.select([m.builds.c.id]))))

            conn.execute(m.logs.delete().where(
                m.logs.c.stepid.notin_(sa.select([m.steps.c.id]))))

            conn.execute(m.logchunks.delete().where(
                m.logchunks.c.logid.notin_(sa.select([m.logs.c.id]))))

    yield db.pool.do(thd)


@defer.inlineCallbacks
def deleteOldBuilders(db, config):
    m = db.model

    def thd(conn):
        with conn.begin():
            # Delete non-active builders that are not referenced by any build.
            conn.execute(m.builders.delete().where(
                m.builders.c.id.notin_(sa.select([m.builder_masters.c.builderid]))
                & m.builders.c.id.notin_(sa.select([m.builds.c.builderid]))))

            # Delete tags not referenced by any builder.
            conn.execute(m.builders_tags.delete().where(
                m.builders_tags.c.builderid.notin_(sa.select([m.builders.c.id]))))

            conn.execute(m.tags.delete().where(
                m.tags.c.id.notin_(sa.select([m.builders_tags.c.tagid]))))

    yield db.pool.do(thd)


@defer.inlineCallbacks
def deleteOldWorkers(db, config):
    m = db.model

    def thd(conn):
        with conn.begin():
            # Delete non-active workers that are not referenced by any build.
            conn.execute(m.workers.delete().where(
                m.workers.c.id.notin_(sa.select([m.configured_workers.c.workerid]))
                & m.workers.c.id.notin_(sa.select([m.builds.c.workerid]))))

    yield db.pool.do(thd)


@defer.inlineCallbacks
def optimizeLogs(db, config):
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


MAINTENANCE_JOBS = (
    ('deleteoldbuilds', deleteOldBuilds),
    ('deleteoldbuilders', deleteOldBuilders),
    ('deleteoldworkers', deleteOldWorkers),
    ('optimizelogs', optimizeLogs),
)


@defer.inlineCallbacks
def doCleanupDatabase(config, master_cfg):
    if not config['quiet']:
        print("cleaning database (%s)" % (master_cfg.db['db_url']))

    master = BuildMaster(config['basedir'])

    master.config = master_cfg
    db = master.db
    yield db.setup(check_version=False, verbose=not config['quiet'])

    for job, func in MAINTENANCE_JOBS:
        if job in config['jobs']:
            print('running job %s...' % job)
            yield func(db, config)

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
