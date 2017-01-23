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

from __future__ import absolute_import
from __future__ import print_function

import sqlalchemy as sa
from migrate import changeset


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    if migrate_engine.dialect.name == "postgresql":
        # changeset.alter_column has no effect on postgres, so we do this with
        # raw sql
        migrate_engine.execute(
            "alter table change_properties alter column property_value type text")

    else:
        # Commit messages can get too big for the normal 1024 String limit.
        changeset.alter_column(
            sa.Column('property_value', sa.Text, nullable=False),
            table='change_properties',
            metadata=metadata,
            engine=migrate_engine)
