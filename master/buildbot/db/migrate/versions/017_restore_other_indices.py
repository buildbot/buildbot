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

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # the column changes in 010_fix_column_lengths.py unfortunately also drop a
    # great deal of other stuff on sqlite.  In particular, all indexes and
    # foreign keys on the 'changes' and 'schedulers' tables.
    #
    # The foreign keys do not matter anyway - SQLite tracks them but ignores
    # them.  The indices, however, are important, so they are re-added here,
    # but only for the sqlite dialect.

    if migrate_engine.dialect.name == 'sqlite':
        schedulers = sautils.Table('schedulers', metadata, autoload=True)

        sa.Index('name_and_class',
                 schedulers.c.name, schedulers.c.class_name).create()

        changes = sautils.Table('changes', metadata, autoload=True)

        sa.Index('changes_branch', changes.c.branch).create()
        sa.Index('changes_revision', changes.c.revision).create()
        sa.Index('changes_author', changes.c.author).create()
        sa.Index('changes_category', changes.c.category).create()
        sa.Index('changes_when_timestamp', changes.c.when_timestamp).create()

        # These were implemented as UniqueConstraint objects, which are
        # recognized as indexes on non-sqlite DB's.  So add them as explicit
        # indexes on sqlite.

        objects = sautils.Table('objects', metadata, autoload=True)
        sa.Index('object_identity', objects.c.name, objects.c.class_name,
                 unique=True).create()

        object_state = sautils.Table('object_state', metadata, autoload=True)
        sa.Index('name_per_object', object_state.c.objectid,
                 object_state.c.name, unique=True).create()

    # Due to a coding bug in version 012, the users_identifier index is not
    # unique (on any DB).  SQLAlchemy-migrate does not provide an interface to
    # drop columns, so we fake it here.

    users = sautils.Table('users', metadata, autoload=True)

    dialect = migrate_engine.dialect.name
    if dialect in ('sqlite', 'postgresql'):
        migrate_engine.execute("DROP INDEX users_identifier")
    elif dialect == 'mysql':
        migrate_engine.execute("DROP INDEX users_identifier ON users")

    sa.Index('users_identifier', users.c.identifier, unique=True).create()
