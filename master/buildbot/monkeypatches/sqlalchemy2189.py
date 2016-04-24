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

import re

from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlalchemy.dialects.sqlite.base import _pragma_cursor
from sqlalchemy.dialects.sqlite.base import sqltypes
from sqlalchemy.dialects.sqlite.base import util
from sqlalchemy.engine import reflection

from buildbot.util import sautils


@reflection.cache
def get_columns_06x_fixed(self, connection, table_name, schema=None, **kw):
    quote = self.identifier_preparer.quote_identifier
    if schema is not None:
        pragma = "PRAGMA %s." % quote(schema)
    else:
        pragma = "PRAGMA "
    qtable = quote(table_name)
    c = _pragma_cursor(
        connection.execute("%stable_info(%s)" % (pragma, qtable)))
    # found_table = False (pyflake)
    columns = []
    while True:
        row = c.fetchone()
        if row is None:
            break
        # BUILDBOT: unused `has_default` removed
        (name, type_, nullable, default, primary_key) = (
            row[1], row[2].upper(), not row[3], row[4], row[5])
        name = re.sub(r'^\"|\"$', '', name)
        # if default:
        #     default = re.sub(r"^\'|\'$", '', default)
        match = re.match(r'(\w+)(\(.*?\))?', type_)
        if match:
            coltype = match.group(1)
            args = match.group(2)
        else:
            coltype = "VARCHAR"
            args = ''
        try:
            coltype = self.ischema_names[coltype]
        except KeyError:
            util.warn("Did not recognize type '%s' of column '%s'" %
                      (coltype, name))
            coltype = sqltypes.NullType
        if args is not None:
            args = re.findall(r'(\d+)', args)
            coltype = coltype(*[int(a) for a in args])

        columns.append({
            'name': name,
            'type': coltype,
            'nullable': nullable,
            'default': default,
            'primary_key': primary_key
        })
    return columns


@reflection.cache
def get_columns_07x_fixed(self, connection, table_name, schema=None, **kw):
    quote = self.identifier_preparer.quote_identifier
    if schema is not None:
        pragma = "PRAGMA %s." % quote(schema)
    else:
        pragma = "PRAGMA "
    qtable = quote(table_name)
    c = _pragma_cursor(
        connection.execute("%stable_info(%s)" % (pragma, qtable)))
    # found_table = False (pyflake)
    columns = []
    while True:
        row = c.fetchone()
        if row is None:
            break
        # BUILDBOT: unused `has_default` removed
        (name, type_, nullable, default, primary_key) = (
            row[1], row[2].upper(), not row[3], row[4], row[5])
        name = re.sub(r'^\"|\"$', '', name)
        # if default:
        #    default = re.sub(r"^\'|\'$", '', default)
        match = re.match(r'(\w+)(\(.*?\))?', type_)
        if match:
            coltype = match.group(1)
            args = match.group(2)
        else:
            coltype = "VARCHAR"
            args = ''
        try:
            coltype = self.ischema_names[coltype]
            if args is not None:
                args = re.findall(r'(\d+)', args)
                coltype = coltype(*[int(a) for a in args])
        except KeyError:
            util.warn("Did not recognize type '%s' of column '%s'" %
                      (coltype, name))
            coltype = sqltypes.NullType()

        columns.append({
            'name': name,
            'type': coltype,
            'nullable': nullable,
            'default': default,
            'autoincrement': default is None,
            'primary_key': primary_key
        })
    return columns


def patch():
    # fix for http://www.sqlalchemy.org/trac/ticket/2189, backported to 0.6.0
    if sautils.sa_version()[:2] == (0, 6):
        get_columns_fixed = get_columns_06x_fixed
    else:
        get_columns_fixed = get_columns_07x_fixed
    SQLiteDialect.get_columns = get_columns_fixed
