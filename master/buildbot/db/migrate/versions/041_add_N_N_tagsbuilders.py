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

    builders = sautils.Table('builders', metadata, autoload=True)
    # drop the tags column
    builders.c.tags.drop()

    tags = sautils.Table(
        'tags', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        # tag's name
        sa.Column('name', sa.Text, nullable=False),
        # sha1 of name; used for a unique index
        sa.Column('name_hash', sa.String(40), nullable=False),
    )

    # a many-to-may relationship between builders and tags
    builders_tags = sautils.Table(
        'builders_tags', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id'),
                  nullable=False),
        sa.Column('tagid', sa.Integer, sa.ForeignKey('tags.id'),
                  nullable=False),
    )

    # create the new tables
    tags.create()
    builders_tags.create()

    # and the indices
    idx = sa.Index('builders_tags_builderid',
                   builders_tags.c.builderid)
    idx.create()
    idx = sa.Index('builders_tags_unique',
                   builders_tags.c.builderid,
                   builders_tags.c.tagid,
                   unique=True)
    idx.create()
    idx = sa.Index('tag_name_hash', tags.c.name_hash, unique=True)
    idx.create()
