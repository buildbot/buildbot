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
from migrate.changeset.constraint import ForeignKeyConstraint
from migrate.exceptions import NotSupportedError

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
    fks_to_change = []
    # we need to parse the reflected model in order to find the automatic fk name that was put
    # mysql and pgsql have different naming convention so this is not very easy to have generic code working.
    for table, keys in [(builder_masters, (builders.c.id, masters.c.id)),
                        (configured_workers, (builder_masters.c.id, workers.c.id))]:
        for fk in table.constraints:
            if not isinstance(fk, sa.ForeignKeyConstraint):
                continue
            for c in fk.elements:
                if c.column in keys:
                    # migrate.xx.ForeignKeyConstraint is changing the model so initializing here
                    # would break the iteration (Set changed size during iteration)
                    fks_to_change.append((
                        table, (fk.columns, [c.column]), dict(name=fk.name, ondelete='CASCADE')))

    for table, args, kwargs in fks_to_change:
        fk = ForeignKeyConstraint(*args, **kwargs)
        table.append_constraint(fk)
        try:
            fk.drop()
        except NotSupportedError:
            pass  # some versions of sqlite do not support drop, but will still update the fk
        fk.create()
