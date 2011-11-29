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

    if migrate_engine.dialect.name != 'sqlite':
        return

    schedulers = sa.Table('schedulers', metadata, autoload=True)

    sa.Index('name_and_class',
            schedulers.c.name, schedulers.c.class_name).create()

    changes = sa.Table('changes', metadata, autoload=True)

    sa.Index('changes_branch', changes.c.branch).create()
    sa.Index('changes_revision', changes.c.revision).create()
    sa.Index('changes_author', changes.c.author).create()
    sa.Index('changes_category', changes.c.category).create()
    sa.Index('changes_when_timestamp', changes.c.when_timestamp).create()

    # Due to a coding bug in version 012, the users_identifier index is not
    # unique

    users = sa.Table('users', metadata, autoload=True)
    migrate_engine.execute("DROP INDEX users_identifier")
    sa.Index('users_identifier', users.c.identifier, unique=True).create()
