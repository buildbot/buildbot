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
from migrate.changeset.constraint import ForeignKeyConstraint

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builders = sautils.Table('builders', metadata, autoload=True)
    masters = sautils.Table('masters', metadata, autoload=True)
    workers = sautils.Table('workers', metadata, autoload=True)
    builder_masters = sautils.Table('builder_masters', metadata, autoload=True)
    configured_workers = sautils.Table('configured_workers', metadata,
                                       autoload=True)

    for fk in (ForeignKeyConstraint([builder_masters.c.builderid],
                                    [builders.c.id], ondelete='CASCADE'),
               ForeignKeyConstraint([builder_masters.c.masterid],
                                    [masters.c.id], ondelete='CASCADE'),
               ForeignKeyConstraint([configured_workers.c.buildermasterid],
                                    [builder_masters.c.id], ondelete='CASCADE'),
               ForeignKeyConstraint([configured_workers.c.workerid],
                                    [workers.c.id], ondelete='CASCADE'),
               ):
        if migrate_engine.dialect.name != 'sqlite':
            fk.drop()
        fk.create()
