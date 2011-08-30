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
from migrate import changeset

def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # Specify what the new table should look like
    schedulers = sa.Table("schedulers", metadata,
        # unique ID for scheduler
        sa.Column('schedulerid', sa.Integer, primary_key=True), # TODO: rename to id
        # scheduler's name in master.cfg
        sa.Column('name', sa.String(128), nullable=False),
        # scheduler's class name, basically representing a "type" for the state
        sa.Column('class_name', sa.String(128), nullable=False),
    )

    # Now drop column
    changeset.drop_column(
            sa.Column('state', sa.String(128), nullable=False),
            table=schedulers,
            metadata=metadata,
            engine=migrate_engine)


