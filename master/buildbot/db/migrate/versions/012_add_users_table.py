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

    # what defines a user
    users = sa.Table("users", metadata,
        sa.Column("uid", sa.Integer, primary_key=True),
        sa.Column("identifier", sa.String(256)),
        sa.Column("full_name", sa.Text()),
        sa.Column("email", sa.Text())
    )
    users.create()

    idx = sa.Index('users_uid', users.c.uid)
    idx.create()
    idx = sa.Index('users_identifier', users.c.identifier)
    idx.create()

    # ways buildbot knows about users
    users_info = sa.Table("users_info", metadata,
        sa.Column("uid", sa.Integer, sa.ForeignKey('users.uid'), nullable=False),
        sa.Column("attr_type", sa.Text(), nullable=False),
        sa.Column("attr_data", sa.Text(), nullable=False)
    )
    users_info.create()

    idx = sa.Index('users_info_uid', users_info.c.uid)
    idx.create()

    # correlates change authors and user uids
    sa.Table('changes', metadata, autoload=True)
    change_users = sa.Table("change_users", metadata,
        sa.Column("changeid", sa.Integer, sa.ForeignKey('changes.changeid'),
                  nullable=False),
        sa.Column("uid", sa.Integer, sa.ForeignKey('users.uid'), nullable=False)
    )
    change_users.create()

    idx = sa.Index('change_users_changeid', change_users.c.changeid)
    idx.create()
