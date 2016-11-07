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
# Copyright Unity Technologies

"""Custom SQLAlchemy types."""

from sqlalchemy import types as sa
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy import TypeDecorator


class LongText(TypeDecorator):
    """Exposes a column as either TEXT in most dialects and LONGTEXT in MySQL."""

    impl = None

    def load_dialect_impl(self, dialect):
        if dialect.name == 'mysql':
            return LONGTEXT()
        return sa.Text()
