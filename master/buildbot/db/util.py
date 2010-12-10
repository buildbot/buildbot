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

def sql_insert(dbapi, table, columns):
    """
    Make an SQL insert statement for the given table and columns, using the
    appropriate paramstyle for the dbi.  Note that this only supports positional
    parameters.  This will need to be reworked if Buildbot supports a backend with
    a name-based paramstyle.
    """

    if dbapi.paramstyle == 'qmark':
        params = ",".join(("?",)*len(columns))
    elif dbapi.paramstyle == 'numeric':
        params = ",".join(":%d" % d for d in range(1, len(columns)+1))
    elif dbapi.paramstyle == 'format':
        params = ",".join(("%s",)*len(columns))
    else:
        raise RuntimeError("unsupported paramstyle %s" % dbapi.paramstyle)
    return "INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(columns), params)
