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
from migrate.changeset import constraint

from buildbot.util import sautils


def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sourcestamps_table = sautils.Table('sourcestamps', metadata, autoload=True)
    buildsets_table = sautils.Table('buildsets', metadata, autoload=True)

    # Create the sourcestampset table
    # that defines a sourcestampset
    sourcestampsets_table = sautils.Table(
        "sourcestampsets", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
    )
    sourcestampsets_table.create()

    # All current sourcestampid's are migrated to sourcestampsetid
    # Insert all sourcestampid's as setid's into sourcestampsets table
    sourcestampsetids = sa.select([sourcestamps_table.c.id])
    # this doesn't seem to work without str() -- verified in sqla 0.6.0 - 0.7.1
    migrate_engine.execute(
        str(sautils.InsertFromSelect(sourcestampsets_table, sourcestampsetids)))

    # rename the buildsets table column
    buildsets_table.c.sourcestampid.alter(name='sourcestampsetid')

    metadata.remove(buildsets_table)
    buildsets_table = sautils.Table('buildsets', metadata, autoload=True)

    cons = constraint.ForeignKeyConstraint([buildsets_table.c.sourcestampsetid], [
                                           sourcestampsets_table.c.id])
    cons.create()

    # Add sourcestampsetid including index to sourcestamps table
    ss_sourcestampsetid = sa.Column('sourcestampsetid', sa.Integer)
    ss_sourcestampsetid.create(sourcestamps_table)

    # Update the setid to the same value as sourcestampid
    migrate_engine.execute(str(sourcestamps_table.update().values(
        sourcestampsetid=sourcestamps_table.c.id)))
    ss_sourcestampsetid.alter(nullable=False)

    # Data is up to date, now force integrity
    cons = constraint.ForeignKeyConstraint([sourcestamps_table.c.sourcestampsetid], [
                                           sourcestampsets_table.c.id])
    cons.create()

    # Add index for performance reasons to find all sourcestamps in a set
    # quickly
    idx = sa.Index('sourcestamps_sourcestampsetid',
                   sourcestamps_table.c.sourcestampsetid, unique=False)
    idx.create()
