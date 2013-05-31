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

def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildrequests_tbl = sa.Table('buildrequests', metadata, autoload=True)
    madebybrid = sa.Column('madebybrid', sa.Integer)
    madebybrid.create(buildrequests_tbl)
    idx = sa.Index('buildrequests_madebybrid', buildrequests_tbl.c.madebybrid, unique=False)
    idx.create()
    # Data is up to date, now force integrity
    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.madebybrid], [buildrequests_tbl.c.id])
    cons.create()

    buildsets_tbl = sa.Table('buildsets', metadata, autoload=True)
    triggeredbybsid = sa.Column('triggeredbybsid', sa.Integer)
    triggeredbybsid.create(buildsets_tbl)
    idx = sa.Index('buildsets_triggeredbybsid', buildsets_tbl.c.triggeredbybsid, unique=False)
    idx.create()
    # Data is up to date, now force integrity
    cons = constraint.ForeignKeyConstraint([buildsets_tbl.c.triggeredbybsid], [buildsets_tbl.c.id])
    cons.create()

    triggeredbybrid = sa.Column('triggeredbybrid', sa.Integer)
    triggeredbybrid.create(buildsets_tbl)
    idx = sa.Index('buildsets_triggeredbybrid', buildsets_tbl.c.triggeredbybrid, unique=False)
    idx.create()
    # Data is up to date, now force integrity
    cons = constraint.ForeignKeyConstraint([buildsets_tbl.c.triggeredbybrid], [buildrequests_tbl.c.id])
    cons.create()

