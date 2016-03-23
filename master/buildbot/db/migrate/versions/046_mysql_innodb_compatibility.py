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
from sqlalchemy.sql import func
from sqlalchemy.sql import or_
from twisted.python import log

from buildbot.util import sautils
from migrate import changeset


def _has_incompatible_changes(metadata, migrate_engine):
    changes = sautils.Table('changes', metadata, autoload=True)
    c = changes.c
    q = sa.select([c.changeid]).where(or_(func.length(c.author) > 255,
                                          func.length(c.branch) > 255,
                                          func.length(c.revision) > 255,
                                          func.length(c.category) > 255))
    invalid_changes = q.execute().fetchall()
    if invalid_changes:

        def format(res):
            return ("changes.change={id} "
                    "have author, branch, revision or category "
                    "longer than 255)".format(id=res[0]))
        log.msg(
            "'changes' table has invalid data:\n"
            "{0}".format("\n".join(map(format, invalid_changes))))
        return True
    return False


def _has_incompatible_object_state(metadata, migrate_engine):
    object_state = sautils.Table('object_state', metadata, autoload=True)
    c = object_state.c
    q = sa.select([c.objectid]).where(func.length(c.name) > 255)
    invalid_object_states = q.execute().fetchall()
    if invalid_object_states:

        def format(res):
            return ("object_state.objectid={id}"
                    " has name longer than 255".format(id=res[0]))
        log.msg(
            "'object_state' table has invalid data:\n"
            "{0}".format("\n".join(map(format, invalid_object_states))))
        return True
    return False


def _has_incompatible_users(metadata, migrate_engine):
    users = sautils.Table('users', metadata, autoload=True)
    c = users.c
    q = sa.select([c.uid]).where(func.length(c.identifier) > 255)
    invalid_users = q.execute().fetchall()
    if invalid_users:

        def format(res):
            return ("users.uid={id} "
                    "has identifier longer than 255".format(id=res[0]))
        log.msg(
            "'users_state' table has invalid data:\n"
            "{0}".format("\n".join(map(format, invalid_users))))
        return True
    return False


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine
    if any([_has_incompatible_changes(metadata, migrate_engine),
            _has_incompatible_object_state(metadata, migrate_engine),
            _has_incompatible_users(metadata, migrate_engine)]):
        raise ValueError('cannot upgrade due to invalid data')
    if migrate_engine.dialect.name == 'postgresql':
        # Sql alchemy migrate does not apply changes on postgresql
        def reduce_table_column_length(table, column):
            return 'ALTER TABLE {} ALTER COLUMN {} TYPE character varying(255)'.format(table, column)
        for table, columns in {'changes': ['author', 'branch', 'revision', 'category'],
                               'object_state': ['name'],
                               'users': ['identifier']}.items():
            for column in columns:
                migrate_engine.execute(reduce_table_column_length(table, column))
        return

    changeset.alter_column(
        sa.Column('author', sa.String(255), nullable=False),
        table='changes',
        metadata=metadata,
        engine=migrate_engine)

    changeset.alter_column(
        sa.Column('branch', sa.String(255)),
        table='changes',
        metadata=metadata,
        engine=migrate_engine)

    changeset.alter_column(
        sa.Column('revision', sa.String(255)),
        table='changes',
        metadata=metadata,
        engine=migrate_engine)

    changeset.alter_column(
        sa.Column('category', sa.String(255)),
        table='changes',
        metadata=metadata,
        engine=migrate_engine)

    changeset.alter_column(
        sa.Column('name', sa.String(255), nullable=False),
        table='object_state',
        metadata=metadata,
        engine=migrate_engine)

    changeset.alter_column(
        sa.Column('identifier', sa.String(255), nullable=False),
        table='users',
        metadata=metadata,
        engine=migrate_engine)
