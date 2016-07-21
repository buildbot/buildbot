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

    users_table = sa.Table('users', metadata, autoload=True)

    fullname = sa.Column('fullname', sa.String(255))
    fullname.create(users_table)
    mail = sa.Column('mail', sa.String(255))
    mail.create(users_table)

    changeset.alter_column(
        sa.Column('identifier', sa.String(255),
                  nullable=False, unique=True),
        table='users', metadata=metadata,
        engine=migrate_engine)
