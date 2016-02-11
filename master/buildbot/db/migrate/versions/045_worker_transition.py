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

import sqlalchemy as sa

from buildbot.util import sautils
from buildbot.db.types.json import JsonObject


def _buildslaves_old_table(table_name, metadata, autoload=False):
    return sautils.Table(
        table_name, metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("info", JsonObject, nullable=False),
        autoload=autoload,
    )


def _builds_old_table(table_name, metadata, autoload=False):
    return sautils.Table(
        table_name, metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id')),
        sa.Column('buildrequestid', sa.Integer, sa.ForeignKey('buildrequests.id'),
                  nullable=False),
        sa.Column('buildslaveid', sa.Integer),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                  nullable=False),
        sa.Column('started_at', sa.Integer, nullable=False),
        sa.Column('complete_at', sa.Integer),
        sa.Column('state_string', sa.Text, nullable=False, server_default=''),
        sa.Column('results', sa.Integer),
        autoload=autoload,
    )


def _connected_buildslaves_old_table(table_name, metadata, autoload=False):
    return sautils.Table(
        table_name, metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id'), nullable=False),
        sa.Column('buildslaveid', sa.Integer, sa.ForeignKey('buildslaves.id'),
                  nullable=False),
        autoload=autoload,
    )


def _configured_buildslaves_old_table(table_name, metadata, autoload=False):
    return sautils.Table(
        table_name, metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('buildermasterid', sa.Integer,
                  sa.ForeignKey('builder_masters.id'), nullable=False),
        sa.Column('buildslaveid', sa.Integer, sa.ForeignKey('buildslaves.id'),
                  nullable=False),
        autoload=autoload,
    )


def _rename_configured_buildslaves_to_old(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    configured_buildslaves = _configured_buildslaves_old_table(
        'configured_buildslaves', metadata, autoload=True)

    for index in configured_buildslaves.indexes:
        index.drop()

    # TODO: I believe there is a reason for doing "rename column" operation
    # as "drop indices; rename table; create new table; migrate data;
    # remove renamed table; create indexes"?
    migrate_engine.execute('alter table configured_buildslaves '
                           'rename to configured_buildslaves_old')


def _rename_connected_buildslaves_to_old(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    connected_buildslaves = _connected_buildslaves_old_table(
        'connected_buildslaves', metadata, autoload=True)

    for index in connected_buildslaves.indexes:
        index.drop()
    migrate_engine.execute('alter table connected_buildslaves '
                           'rename to connected_buildslaves_old')


def _rename_buildslaves_to_old(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildslaves = _buildslaves_old_table(
        'buildslaves', metadata, autoload=True)

    for index in buildslaves.indexes:
        index.drop()
    migrate_engine.execute('alter table buildslaves '
                           'rename to buildslaves_old')


def _rename_builds_to_old(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds = _builds_old_table('builds', metadata, autoload=True)

    for index in builds.indexes:
        index.drop()
    migrate_engine.execute('alter table builds '
                           'rename to builds_old')


def _create_configured_workers_table(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # TODO: instead of specifying table definition every time
    # (as done is some other migrations), I'm using autoloading
    # of the metadata from database.
    # Is this correct?
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

    # TODO: instead of specifying table definition every time
    # (as done is some other migrations), I'm using autoloading
    # of the metadata from database.
    # Is this correct?
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


def _create_builds_table(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('builders', metadata, autoload=True)
    sautils.Table('buildrequests', metadata, autoload=True)
    sautils.Table('workers', metadata, autoload=True)
    sautils.Table('masters', metadata, autoload=True)

    # Create 'builds' table.
    builds = sautils.Table(
        'builds', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id')),
        sa.Column('buildrequestid', sa.Integer, sa.ForeignKey('buildrequests.id'),
                  nullable=False),
        sa.Column('workerid', sa.Integer, sa.ForeignKey('workers.id')),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
                  nullable=False),
        sa.Column('started_at', sa.Integer, nullable=False),
        sa.Column('complete_at', sa.Integer),
        sa.Column('state_string', sa.Text, nullable=False, server_default=''),
        sa.Column('results', sa.Integer),
    )
    builds.create()

    # Create indexes.
    idx = sa.Index('builds_buildrequestid', builds.c.buildrequestid)
    idx.create()

    idx = sa.Index('builds_number',
                   builds.c.builderid, builds.c.number,
                   unique=True)
    idx.create()

    idx = sa.Index('builds_workerid',
                   builds.c.workerid)
    idx.create()

    idx = sa.Index('builds_masterid',
                   builds.c.masterid)
    idx.create()


def _migrate_workers_table_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildslaves_old = _buildslaves_old_table('buildslaves_old', metadata)
    workers = sautils.Table('workers', metadata, autoload=True)

    c = buildslaves_old.c
    q = sa.select([c.id, c.name, c.info])

    # TODO: this doesn't seem to work without str() -- verified in sqla 0.6.0 - 0.7.1
    # (this comment from 011_add_buildrequest_claims.py)
    migrate_engine.execute(
        str(sautils.InsertFromSelect(workers, q)))


def _migrate_configured_workers_table_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    configured_buildslaves_old = _configured_buildslaves_old_table(
        'configured_buildslaves_old', metadata)
    configured_workers = sautils.Table(
        'configured_workers', metadata, autoload=True)

    c = configured_buildslaves_old.c
    q = sa.select([c.id, c.buildermasterid, c.buildslaveid.label('workerid')])

    # TODO: this doesn't seem to work without str() -- verified in sqla 0.6.0 - 0.7.1
    # (this comment from 011_add_buildrequest_claims.py)
    migrate_engine.execute(
        str(sautils.InsertFromSelect(configured_workers, q)))


def _migrate_connected_workers_table_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    connected_buildslaves_old = _connected_buildslaves_old_table(
        'connected_buildslaves_old', metadata)
    connected_workers = sautils.Table(
        'connected_workers', metadata, autoload=True)

    c = connected_buildslaves_old.c
    q = sa.select([c.id, c.masterid, c.buildslaveid.label('workerid')])

    # TODO: this doesn't seem to work without str() -- verified in sqla 0.6.0 - 0.7.1
    # (this comment from 011_add_buildrequest_claims.py)
    migrate_engine.execute(
        str(sautils.InsertFromSelect(connected_workers, q)))


def _migrate_builds_table_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds_old = _builds_old_table('builds_old', metadata)
    builds = sautils.Table('builds', metadata, autoload=True)

    c = builds_old.c
    q = sa.select([
        c.id,
        c.number,
        c.builderid,
        c.buildrequestid,
        c.buildslaveid.label('workerid'),
        c.masterid,
        c.started_at,
        c.complete_at,
        c.state_string,
        c.results
    ])

    # TODO: this doesn't seem to work without str() -- verified in sqla 0.6.0 - 0.7.1
    # (this comment from 011_add_buildrequest_claims.py)
    migrate_engine.execute(
        str(sautils.InsertFromSelect(builds, q)))


def _drop_old_configured_buildslaves(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    configured_buildslaves_old = _configured_buildslaves_old_table(
        'configured_buildslaves_old', metadata)
    configured_buildslaves_old.drop()


def _drop_old_connected_buildslaves(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    connected_buildslaves_old = _connected_buildslaves_old_table(
        'connected_buildslaves_old', metadata)
    connected_buildslaves_old.drop()


def _drop_old_builds(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds_old = _builds_old_table('builds_old', metadata)
    builds_old.drop()


def _drop_old_buildslaves(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildslaves_old = _buildslaves_old_table(
        'buildslaves_old', metadata)
    buildslaves_old.drop()


def _validate_builds_buildslaves(migrate_engine):
    # This is consistency check for issue #3088:
    # 'buildslaveid' column of 'builds' table don't have Foreign Key
    # constraint on 'id' column of 'buildslaves' table, so it is
    # possible that that reference is invalid.
    # TODO: Maybe just skip invalid references?

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds = sautils.Table('builds', metadata, autoload=True)
    buildslaves = sautils.Table('buildslaves', metadata, autoload=True)

    q = sa.select(
        [builds.c.id, builds.c.buildslaveid, buildslaves.c.id]
    ).select_from(
        builds.outerjoin(buildslaves, builds.c.buildslaveid == buildslaves.c.id)
    ).where(
        (buildslaves.c.id == None) & (builds.c.buildslaveid != None)
    )

    invalid_references = q.execute().fetchall()
    if invalid_references:
        def format(res):
            return ("builds.id={id} builds.buildslaveid={buildslaveid} "
                    "(not present in 'buildslaves' table)").format(
                id=res[0], buildslaveid=res[1])
        raise RuntimeError(
            "'builds' table has invalid references on 'buildslaves' table:\n"
            "{0}".format("\n".join(map(format, invalid_references))))


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # Validate builds -> buildslaves relation.
    _validate_builds_buildslaves(migrate_engine)

    _rename_configured_buildslaves_to_old(migrate_engine)
    _rename_connected_buildslaves_to_old(migrate_engine)
    _rename_buildslaves_to_old(migrate_engine)
    _rename_builds_to_old(migrate_engine)

    _create_workers_table(migrate_engine)
    _create_configured_workers_table(migrate_engine)
    _create_connected_workers_table(migrate_engine)
    _create_builds_table(migrate_engine)

    _migrate_workers_table_data(migrate_engine)
    _migrate_configured_workers_table_data(migrate_engine)
    _migrate_connected_workers_table_data(migrate_engine)
    _migrate_builds_table_data(migrate_engine)

    _drop_old_builds(migrate_engine)
    _drop_old_connected_buildslaves(migrate_engine)
    _drop_old_configured_buildslaves(migrate_engine)
    _drop_old_buildslaves(migrate_engine)
