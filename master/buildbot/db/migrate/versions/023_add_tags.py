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
from buildbot.util import sautils

def migrate_categories_to_tags(migrate_engine, changes, tags, change_tags):
    # 1. Convert categories to a unique set of tags.
    unique_tags = sa.select(
                      [changes.c.category]
                  ).where(changes.c.category != None).group_by(changes.c.category)
    migrate_engine.execute(str(sautils.InsertColumnsFromSelect(tags, tags.c.tag.name, unique_tags)))

    # 2. Fill the change_tags relation to match the changes and tags.
    change_tags_rel = sa.select(
                          [
                              changes.c.changeid,
                              tags.c.id.label('tagid')
                          ],
                          changes.c.category == tags.c.tag)
    migrate_engine.execute(str(sautils.InsertFromSelect(change_tags, change_tags_rel)))

def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    changes = sa.Table('changes', metadata, autoload=True)

    # Create new tables and indices.
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

    migrate_categories_to_tags(migrate_engine, changes, tags, change_tags)

    # Now drop the category column.
    index_to_drop = sa.Index('changes_category', changes.c.category)
    index_to_drop.drop()
    changes.c.category.drop()
