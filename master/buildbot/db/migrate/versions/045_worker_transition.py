# This file is part of Buildbot. Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function

import sqlalchemy as sa

from twisted.python import log

from buildbot.db.types.json import JsonObject
from buildbot.util import sautils


def _create_configured_workers_table(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('builder_masters', metadata, autoload=True)
    sautils.Table('workers', metadata, autoload=True)

    # Create 'configured_workers' table.
    configured_workers = sautils.Table(
        'configured_workers', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('buildermasterid', sa.Integer,
                  sa.ForeignKey('builder_masters.id'), nullable=False),
        sa.Column('workerid', sa.Integer, sa.ForeignKey('workers.id'),
                  nullable=False),
    )
    configured_workers.create()

    # Create indexes.
    idx = sa.Index('configured_workers_buildmasterid',
                   configured_workers.c.buildermasterid)
    idx.create()

    idx = sa.Index('configured_workers_workers',
                   configured_workers.c.workerid)
    idx.create()

    idx = sa.Index('configured_workers_identity',
                   configured_workers.c.buildermasterid,
                   configured_workers.c.workerid, unique=True)
    idx.create()


def _create_connected_workers_table(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('masters', metadata, autoload=True)
    sautils.Table('workers', metadata, autoload=True)

    # Create 'connected_workers' table.
    connected_workers = sautils.Table(
        'connected_workers', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id'), nullable=False),
        sa.Column('workerid', sa.Integer, sa.ForeignKey('workers.id'),
                  nullable=False),
    )
    connected_workers.create()

    # Create indexes.
    idx = sa.Index('connected_workers_masterid',
                   connected_workers.c.masterid)
    idx.create()

    idx = sa.Index('connected_workers_workers',
                   connected_workers.c.workerid)
    idx.create()

    idx = sa.Index('connected_workers_identity',
                   connected_workers.c.masterid,
                   connected_workers.c.workerid, unique=True)
    idx.create()


def _create_workers_table(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # Create 'workers' table.
    workers = sautils.Table(
        "workers", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("info", JsonObject, nullable=False),
    )
    workers.create()

    # Create indexes.
    idx = sa.Index('workers_name', workers.c.name, unique=True)
    idx.create()


def _add_workerid_fk_to_builds_table(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('builders', metadata, autoload=True)
    sautils.Table('buildrequests', metadata, autoload=True)
    sautils.Table('workers', metadata, autoload=True)
    sautils.Table('masters', metadata, autoload=True)

    builds = sautils.Table('builds', metadata, autoload=True)

    workerid = sa.Column('workerid', sa.Integer, sa.ForeignKey('workers.id'))
    workerid.create(builds)

    # Create indexes.
    idx = sa.Index('builds_workerid',
                   builds.c.workerid)
    idx.create()


def _migrate_workers_table_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildslaves = sautils.Table('buildslaves', metadata, autoload=True)
    workers = sautils.Table('workers', metadata, autoload=True)

    c = buildslaves.c
    q = sa.select([c.id, c.name, c.info])

    migrate_engine.execute(
        str(sautils.InsertFromSelect(workers, q)))


def _migrate_configured_workers_table_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    configured_buildslaves = sautils.Table(
        'configured_buildslaves', metadata, autoload=True)
    configured_workers = sautils.Table(
        'configured_workers', metadata, autoload=True)

    c = configured_buildslaves.c
    q = sa.select([c.id, c.buildermasterid, c.buildslaveid.label('workerid')])

    migrate_engine.execute(
        str(sautils.InsertFromSelect(configured_workers, q)))


def _migrate_connected_workers_table_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    connected_buildslaves = sautils.Table(
        'connected_buildslaves', metadata, autoload=True)
    connected_workers = sautils.Table(
        'connected_workers', metadata, autoload=True)

    c = connected_buildslaves.c
    q = sa.select([c.id, c.masterid, c.buildslaveid.label('workerid')])

    migrate_engine.execute(
        str(sautils.InsertFromSelect(connected_workers, q)))


def _migrate_builds_table_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds = sautils.Table('builds', metadata, autoload=True)

    s = builds.update().values(workerid=builds.c.buildslaveid)
    migrate_engine.execute(s)


def _drop_configured_buildslaves(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    configured_buildslaves = sautils.Table(
        'configured_buildslaves', metadata, autoload=True)
    configured_buildslaves.drop()


def _drop_connected_buildslaves(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    connected_buildslaves = sautils.Table(
        'connected_buildslaves', metadata, autoload=True)
    connected_buildslaves.drop()


def _drop_buildslaveid_column_in_builds(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds = sautils.Table('builds', metadata, autoload=True)

    builds.c.buildslaveid.drop()


def _drop_buildslaves(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildslaves_old = sautils.Table('buildslaves', metadata, autoload=True)
    buildslaves_old.drop()


def _remove_invalid_references_in_builds(migrate_engine):
    # 'buildslaveid' column of 'builds' table don't have Foreign Key
    # constraint on 'id' column of 'buildslaves' table, so it is
    # possible that that reference is invalid.
    # Remove such invalid references for easier resolve of #3088 later.

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds = sautils.Table('builds', metadata, autoload=True)
    buildslaves = sautils.Table('buildslaves', metadata, autoload=True)

    q = sa.select(
        [builds.c.id, builds.c.buildslaveid, buildslaves.c.id]
    ).select_from(
        builds.outerjoin(
            buildslaves, builds.c.buildslaveid == buildslaves.c.id)
    ).where(
        (buildslaves.c.id == None) & (builds.c.buildslaveid != None)
    )

    invalid_references = q.execute().fetchall()
    if invalid_references:
        # Report invalid references.
        def format(res):
            return ("builds.id={id} builds.buildslaveid={buildslaveid} "
                    "(not present in 'buildslaves' table)").format(
                id=res[0], buildslaveid=res[1])
        log.msg(
            "'builds' table has invalid references on 'buildslaves' table:\n"
            "{0}".format("\n".join(map(format, invalid_references))))

        # Remove invalid references.
        for build_id, buildslave_id, none in invalid_references:
            assert none is None
            q = sa.update(builds).where(builds.c.id == build_id).values(
                buildslaveid=None)
            q.execute()


def upgrade(migrate_engine):
    # DB schema in version 044:
    #
    # buildslaves:
    #     ...
    #
    # builds:
    #     buildslaveid: Integer
    #     ...
    #
    # configured_buildslaves:
    #     buildslaveid: Integer, ForeignKey('buildslaves.id')
    #     ...
    #
    # connected_buildslaves:
    #     buildslaveid: Integer, ForeignKey('buildslaves.id')
    #     ...
    #
    # Desired DB schema in version 045:
    #
    # workers:
    #     ...
    #
    # builds:
    #     workerid: Integer, ForeignKey('workers.id')
    #     ...
    #
    # configured_workers:
    #     workerid: Integer, ForeignKey('workers.id')
    #     ...
    #
    # connected_workers:
    #     workerid: Integer, ForeignKey('workers.id')
    #     ...
    #
    # So we need to rename three tables, references to them, and add new
    # foreign key (issue #3088).
    # Plus indexes must be renamed/recreated.
    #
    # There is no external references on tables that being renamed
    # (i.e. on 'buildslaves', 'configured_buildslaves',
    # 'connected_buildslaves'), so we can safely recreate them without worrying
    # that ForeignKey constraints will be violated.

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # Remove invalid references in builds -> buildslaves relation.
    _remove_invalid_references_in_builds(migrate_engine)

    _create_workers_table(migrate_engine)
    _create_configured_workers_table(migrate_engine)
    _create_connected_workers_table(migrate_engine)
    _add_workerid_fk_to_builds_table(migrate_engine)

    _migrate_workers_table_data(migrate_engine)
    _migrate_configured_workers_table_data(migrate_engine)
    _migrate_connected_workers_table_data(migrate_engine)
    _migrate_builds_table_data(migrate_engine)

    _drop_buildslaveid_column_in_builds(migrate_engine)
    _drop_connected_buildslaves(migrate_engine)
    _drop_configured_buildslaves(migrate_engine)
    _drop_buildslaves(migrate_engine)
