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

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('builds', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  # ..
                  )

    # This table contains input properties for builds
    build_properties = sautils.Table(
        'build_properties', metadata,
        sa.Column('buildid', sa.Integer, sa.ForeignKey('builds.id'), nullable=False),
        sa.Column('name', sa.String(256), nullable=False),
        # JSON-encoded value
        sa.Column('value', sa.Text, nullable=False),
        sa.Column('source', sa.Text, nullable=False),
    )

    # create the new table
    build_properties.create()

    # and an Index on it.
    idx = sa.Index('build_properties_buildid', build_properties.c.buildid)
    idx.create()
