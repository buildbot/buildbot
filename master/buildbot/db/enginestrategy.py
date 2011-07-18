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

"""
A wrapper around `sqlalchemy.create_engine` that handles all of the
special cases that Buildbot needs.  Those include:

 - pool_recycle for MySQL
 - %(basedir) substitution
 - optimal thread pool size calculation

"""

import os
import sqlalchemy
from twisted.python import log
from sqlalchemy.engine import strategies, url
from sqlalchemy.pool import NullPool

# from http://www.mail-archive.com/sqlalchemy@googlegroups.com/msg15079.html
class ReconnectingListener(object):
    def __init__(self):
        self.retried = False
    def checkout(self, dbapi_con, con_record, con_proxy):
        try:
            try:
                dbapi_con.ping(False)
            except TypeError:
                dbapi_con.ping()
        except dbapi_con.OperationalError, ex:
            if ex.args[0] in (2006, 2013, 2014, 2045, 2055):
                # sqlalchemy will re-create the connection
                raise sqlalchemy.exc.DisconnectionError()
            raise

class BuildbotEngineStrategy(strategies.ThreadLocalEngineStrategy):
    """
    A subclass of the ThreadLocalEngineStrategy that can effectively interact
    with Buildbot.

    This adjusts the passed-in parameters to ensure that we get the behaviors
    Buildbot wants from particular drivers, and wraps the outgoing Engine
    object so that its methods run in threads and return deferreds.
    """

    name = 'buildbot'

    def special_case_sqlite(self, u, kwargs):
        """For sqlite, percent-substitute %(basedir)s and use a full
        path to the basedir.  If using a memory database, force the
        pool size to be 1."""
        max_conns = None

        # when given a database path, stick the basedir in there
        if u.database:

            # Use NullPool instead of the sqlalchemy-0.6.8-default
            # SingletonThreadpool for sqlite to suppress the error in
            # http://groups.google.com/group/sqlalchemy/msg/f8482e4721a89589,
            # which also explains that NullPool is the new default in
            # sqlalchemy 0.7 for non-memory SQLite databases.
            kwargs.setdefault('poolclass', NullPool)

            u.database = u.database % dict(basedir = kwargs['basedir'])
            if not os.path.isabs(u.database[0]):
                u.database = os.path.join(kwargs['basedir'], u.database)

        # in-memory databases need exactly one connection
        if not u.database:
            kwargs['pool_size'] = 1
            max_conns = 1

        # allow serializing access to the db
        if 'serialize_access' in u.query:
            u.query.pop('serialize_access')
            max_conns = 1

        return u, kwargs, max_conns

    def set_up_sqlite_engine(self, u, engine):
        """Special setup for sqlite engines"""
        # try to enable WAL logging
        if u.database:
            log.msg("setting database journal mode to 'wal'")
            try:
                engine.execute("pragma journal_mode = wal")
            except:
                log.msg("failed to set journal mode - database may fail")

    def special_case_mysql(self, u, kwargs):
        """For mysql, take max_idle out of the query arguments, and
        use its value for pool_recycle.  Also, force use_unicode and
        charset to be True and 'utf8', failing if they were set to
        anything else."""

        kwargs['pool_recycle'] = int(u.query.pop('max_idle', 3600))

        # default to the InnoDB storage engine
        storage_engine = u.query.pop('storage_engine', 'MyISAM')
        kwargs['connect_args'] = {
            'init_command' : 'SET storage_engine=%s' % storage_engine,
        }

        if 'use_unicode' in u.query:
            if u.query['use_unicode'] != "True":
                raise TypeError("Buildbot requires use_unicode=True " +
                                 "(and adds it automatically)")
        else:
            u.query['use_unicode'] = True

        if 'charset' in u.query:
            if u.query['charset'] != "utf8":
                raise TypeError("Buildbot requires charset=utf8 " +
                                 "(and adds it automatically)")
        else:
            u.query['charset'] = 'utf8'

        # add the reconnecting PoolListener that will detect a
        # disconnected connection and automatically start a new
        # one.  This provides a measure of additional safety over
        # the pool_recycle parameter, and is useful when e.g., the
        # mysql server goes away
        kwargs['listeners'] = [ ReconnectingListener() ]

        return u, kwargs, None

    def create(self, name_or_url, **kwargs):
        if 'basedir' not in kwargs:
            raise TypeError('no basedir supplied to create_engine')

        max_conns = None

        # apply special cases
        u = url.make_url(name_or_url)
        if u.drivername.startswith('sqlite'):
            u, kwargs, max_conns = self.special_case_sqlite(u, kwargs)
        elif u.drivername.startswith('mysql'):
            u, kwargs, max_conns = self.special_case_mysql(u, kwargs)

        # remove the basedir as it may confuse sqlalchemy
        basedir = kwargs.pop('basedir')

        # calculate the maximum number of connections from the pool parameters,
        # if it hasn't already been specified
        if max_conns is None:
            max_conns = kwargs.get('pool_size', 5) + kwargs.get('max_overflow', 10)

        engine = strategies.ThreadLocalEngineStrategy.create(self,
                                            u, **kwargs)

        # annotate the engine with the optimal thread pool size; this is used
        # by DBConnector to configure the surrounding thread pool
        engine.optimal_thread_pool_size = max_conns

        # keep the basedir
        engine.buildbot_basedir = basedir

        if u.drivername.startswith('sqlite'):
            self.set_up_sqlite_engine(u, engine)

        return engine

BuildbotEngineStrategy()

# this module is really imported for the side-effects, but pyflakes will like
# us to use something from the module -- so offer a copy of create_engine, which
# explicitly adds the strategy argument
def create_engine(*args, **kwargs):
    kwargs['strategy'] = 'buildbot'

    return sqlalchemy.create_engine(*args, **kwargs)
