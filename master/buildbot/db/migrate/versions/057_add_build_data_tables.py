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


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table(
        'builds', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        # ...
    )

    build_data = sautils.Table(
        'build_data', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('buildid', sa.Integer,
                  sa.ForeignKey('builds.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('value', sa.LargeBinary().with_variant(sa.dialects.mysql.LONGBLOB, "mysql"),
                  nullable=False),
        sa.Column('source', sa.String(256), nullable=False),
    )

    # create the tables
    build_data.create()

    # create indexes
    idx = sa.Index('build_data_buildid_name', build_data.c.buildid, build_data.c.name, unique=True)
    idx.create()
