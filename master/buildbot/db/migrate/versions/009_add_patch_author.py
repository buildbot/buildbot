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


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # add patch_author and patch_comment to the patches table

    # mysql doesn't like default values on these columns
    defaults = {}
    if migrate_engine.dialect.name != "mysql":
        defaults['server_default'] = sa.DefaultClause('')

    patches = sautils.Table('patches', metadata, autoload=True)
    patch_author = sa.Column('patch_author', sa.Text, nullable=False,
                             **defaults)
    patch_author.create(patches, populate_default=True)

    patch_author = sa.Column('patch_comment', sa.Text, nullable=False,
                             **defaults)
    patch_author.create(patches, populate_default=True)
