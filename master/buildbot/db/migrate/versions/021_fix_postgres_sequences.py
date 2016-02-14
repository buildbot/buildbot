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
    # see bug #2119

    # this only applies to postgres
    if migrate_engine.dialect.name != 'postgresql':
        return

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    to_fix = [
        'buildrequests.id',
        'builds.id',
        'buildsets.id',
        'changes.changeid',
        'patches.id',
        'sourcestampsets.id',
        'sourcestamps.id',
        'objects.id',
        'users.uid',
    ]

    for col in to_fix:
        tbl_name, col_name = col.split('.')
        tbl = sautils.Table(tbl_name, metadata, autoload=True)
        col = tbl.c[col_name]

        res = migrate_engine.execute(sa.select([sa.func.max(col)]))
        max = res.fetchall()[0][0]

        if max:
            seq_name = "%s_%s_seq" % (tbl_name, col_name)
            r = migrate_engine.execute("SELECT setval('%s', %d)"
                                       % (seq_name, max))
            r.close()
