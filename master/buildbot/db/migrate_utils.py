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
from future.utils import text_type

import sqlalchemy as sa

from buildbot.util import sautils


def test_unicode(migrate_engine):
    """Test that the database can handle inserting and selecting Unicode"""
    # set up a subsidiary MetaData object to hold this temporary table
    submeta = sa.MetaData()
    submeta.bind = migrate_engine

    test_unicode = sautils.Table(
        'test_unicode', submeta,
        sa.Column('u', sa.Unicode(length=100)),
        sa.Column('b', sa.LargeBinary),
    )
    test_unicode.create()

    # insert a unicode value in there
    u = u"Frosty the \N{SNOWMAN}"
    b = b'\xff\xff\x00'
    ins = test_unicode.insert().values(u=u, b=b)
    migrate_engine.execute(ins)

    # see if the data is intact
    row = migrate_engine.execute(sa.select([test_unicode])).fetchall()[0]
    assert isinstance(row['u'], text_type)
    assert row['u'] == u
    assert isinstance(row['b'], bytes)
    assert row['b'] == b

    # drop the test table
    test_unicode.drop()
