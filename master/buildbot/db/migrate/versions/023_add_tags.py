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

    changes = sa.Table('changes', metadata, autoload=True)

    tags = sa.Table('tags', metadata,
        sa.Column('id',  sa.Integer,     primary_key=True),
        sa.Column('tag', sa.String(256), nullable=False),
    )
    tags.create()

    idx = sa.Index('tags_tag', tags.c.tag, unique=True)
    idx.create()

    change_tags = sa.Table('change_tags', metadata,
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'),
            primary_key=True),
        sa.Column('tagid', sa.Integer, sa.ForeignKey('tags.id'),
            primary_key=True)
    )
    change_tags.create()

    idx = sa.Index('change_tags_tagid', change_tags.c.tagid)
    idx.create()
