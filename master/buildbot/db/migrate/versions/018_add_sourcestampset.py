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
import migrate
from migrate.changeset import constraint
from buildbot.util import sautils

def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sourcestamps_table = sa.Table('sourcestamps', metadata, autoload=True)
    buildsets_table = sa.Table('buildsets', metadata, autoload=True)

    # Create the sourcestampset table
    # that defines a sourcestampset
    sourcestampsets_table = sa.Table("sourcestampsets", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
    )
    sourcestampsets_table.create()

    # All current sourcestampid's are migrated to sourcestampsetid
    # Insert all sourcestampid's as setid's into sourcestampsets table
    sourcestampsetids = sa.select([sourcestamps_table.c.id])
    # this doesn't seem to work without str() -- verified in sqla 0.6.0 - 0.7.1
    migrate_engine.execute(str(sautils.InsertFromSelect(sourcestampsets_table, sourcestampsetids)))

    tmp_buildsets = sa.Table('tmp_buildsets', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),
        sa.Column('external_idstring', sa.String(256)),
        sa.Column('reason', sa.String(256)), # TODO: sa.Text
        sa.Column('sourcestampid', sa.Integer, nullable=False),
        sa.Column('submitted_at', sa.Integer, nullable=False), # TODO: redundant
        sa.Column('complete', sa.SmallInteger, nullable=False, server_default=sa.DefaultClause("0")), # TODO: redundant
        sa.Column('complete_at', sa.Integer), # TODO: redundant
        sa.Column('results', sa.SmallInteger), # TODO: synthesize from buildrequests
    )
    tmp_buildsets.create()

    sets=sa.select([ buildsets_table.c.id,
                    buildsets_table.c.external_idstring,
                    buildsets_table.c.reason,
                    buildsets_table.c.sourcestampid,
                    buildsets_table.c.submitted_at,
                    buildsets_table.c.complete,
                    buildsets_table.c.complete_at,
                    buildsets_table.c.results
        ])
    migrate_engine.execute(str(sautils.InsertFromSelect(tmp_buildsets, sets)))

    # Drop the old one
    buildsets_table.drop()
    metadata.remove(buildsets_table)
    # Create the new one
    new_buildsets = sa.Table('buildsets', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),
        sa.Column('external_idstring', sa.String(256)),
        sa.Column('reason', sa.String(256)), # TODO: sa.Text
        sa.Column('sourcestampsetid', sa.Integer, sa.ForeignKey('sourcestampsets.id'), nullable=False),
        sa.Column('submitted_at', sa.Integer, nullable=False), # TODO: redundant
        sa.Column('complete', sa.SmallInteger, nullable=False, server_default=sa.DefaultClause("0")), # TODO: redundant
        sa.Column('complete_at', sa.Integer), # TODO: redundant
        sa.Column('results', sa.SmallInteger),
    )
    new_buildsets.create()
    # Recreate the indexes
    sa.Index('buildsets_complete', new_buildsets.c.complete).create()
    sa.Index('buildsets_submitted_at', new_buildsets.c.submitted_at).create()
    newsets=sa.select([tmp_buildsets.c.id,
                    tmp_buildsets.c.external_idstring,
                    tmp_buildsets.c.reason,
                    tmp_buildsets.c.sourcestampid.label("sourcestampsetid"),
                    tmp_buildsets.c.submitted_at,
                    tmp_buildsets.c.complete,
                    tmp_buildsets.c.complete_at,
                    tmp_buildsets.c.results
        ])
    migrate_engine.execute(str(sautils.InsertFromSelect(new_buildsets, newsets)))

    tmp_buildsets.drop();
    metadata.remove(tmp_buildsets)

    # Add sourcestampsetid including index to sourcestamps table
    ss_sourcestampsetid = sa.Column('sourcestampsetid', sa.Integer)
    ss_sourcestampsetid.create(sourcestamps_table)
    
    # Update the setid to the same value as sourcestampid
    migrate_engine.execute(str(sourcestamps_table.update().values(sourcestampsetid=sourcestamps_table.c.id)))
    ss_sourcestampsetid.alter(nullable=False)
    # Data is up to date, now force integrity
    cons = constraint.ForeignKeyConstraint([sourcestamps_table.c.sourcestampsetid], [sourcestampsets_table.c.id])
    cons.create()

    # Add index for performance reasons to find all sourcestamps in a set quickly
    idx = sa.Index('sourcestamps_sourcestampsetid', sourcestamps_table.c.sourcestampsetid, unique=False)
    idx.create()
