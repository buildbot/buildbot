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


def patch():
    # a fix for http://www.sqlalchemy.org/trac/ticket/2364
    from sqlalchemy.dialects.sqlite.base import SQLiteDialect
    old_get_foreign_keys = SQLiteDialect.get_foreign_keys

    def get_foreign_keys_wrapper(*args, **kwargs):
        fkeys = old_get_foreign_keys(*args, **kwargs)
        # foreign keys don't have names
        for fkey in fkeys:
            fkey['name'] = None
        return fkeys
    SQLiteDialect.get_foreign_keys = get_foreign_keys_wrapper
