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

from sqlalchemy.dialects import mysql
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Query

class DBConnectorComponent(object):
    # A fixed component of the DBConnector, handling one particular aspect of
    # the database.  Instances of subclasses are assigned to attributes of the
    # DBConnector object, so that they are available at e.g.,
    # C{master.db.model} or C{master.db.changes}.  This parent class takes care
    # of the necessary backlinks and other housekeeping.

    connector = None

    def __init__(self, connector):
        self.db = connector

        # set up caches
        for method in dir(self.__class__):
            o = getattr(self, method)
            if isinstance(o, CachedMethod):
                setattr(self, method, o.get_cached_method(self))

    _is_check_length_necessary = None
    def check_length(self, col, value):
        # for use by subclasses to check that 'value' will fit in 'col', where
        # 'col' is a table column from the model.

        # ignore this check for database engines that either provide this error
        # themselves (postgres) or that do not enforce maximum-length
        # restrictions (sqlite)
        if not self._is_check_length_necessary:
            if self.db.pool.engine.dialect.name == 'mysql':
                self._is_check_length_necessary = True
            else:
                # not necessary, so just stub out the method
                self.check_length = lambda col, value : None
                return

        assert col.type.length, "column %s does not have a length" % (col,)
        if value and len(value) > col.type.length:
            raise RuntimeError(
                "value for column %s is greater than max of %d characters: %s"
                    % (col, col.type.length, value))

    def truncateColumn(self, col, value):
        col_length = col.type.length - 2
        return value[:col_length] + '..' if len(value) > col_length else value

    # Utility method that generates the sqlalchemy expression to SQL statement
    # only used for debugging purpose
    def getSQLExpression(self, statement, dialect=None):
        if isinstance(statement, Query):
            if dialect is None:
                dialect = statement.session.get_bind(
                    statement._mapper_zero_or_none()
                ).dialect
            statement = statement.statement
        if dialect is None:
            dialect = getattr(statement.bind, 'dialect', None)
        if dialect is None:
            dialect = mysql.dialect()

        Compiler = type(statement._compiler(dialect))

        class LiteralCompiler(Compiler):
            visit_bindparam = Compiler.render_literal_bindparam

            def render_literal_value(self, value, type_):
                if isinstance(value, (Decimal, long)):
                    return str(value)
                elif isinstance(value, datetime):
                    return repr(str(value))
                else:  # fallback
                    value = super(LiteralCompiler, self).render_literal_value(
                        value, type_,
                    )
                    if isinstance(value, unicode):
                        return value.encode('UTF-8')
                    else:
                        return value

        return LiteralCompiler(dialect, statement)

class CachedMethod(object):
    def __init__(self, cache_name, method):
        self.cache_name = cache_name
        self.method = method

    def get_cached_method(self, component):
        meth = self.method

        meth_name = meth.__name__
        cache = component.db.master.caches.get_cache(self.cache_name,
                lambda key : meth(component, key))
        def wrap(key, no_cache=0):
            if no_cache:
                return meth(component, key)
            return cache.get(key)
        wrap.__name__ = meth_name + " (wrapped)"
        wrap.__module__ = meth.__module__
        wrap.__doc__ = meth.__doc__
        wrap.cache = cache
        return wrap

def cached(cache_name):
    return lambda method : CachedMethod(cache_name, method)
