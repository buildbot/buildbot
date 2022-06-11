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

import sqlalchemy as sa
from sqlalchemy.engine import url
from sqlalchemy.pool import NullPool

from twisted.python import log

from buildbot.util import sautils

# from http://www.mail-archive.com/sqlalchemy@googlegroups.com/msg15079.html


class ReconnectingListener:

    def __init__(self):
        self.retried = False


class Strategy:

    def set_up(self, u, engine):
        pass

    def should_retry(self, operational_error):
        try:
            text = operational_error.args[0]
            return 'Lost connection' in text or 'database is locked' in text
        except Exception:
            return False


class SqlLiteStrategy(Strategy):

    def set_up(self, u, engine):
        """Special setup for sqlite engines"""
        def connect_listener_enable_fk(connection, record):
            # fk must be enabled for all connections
            if not getattr(engine, "fk_disabled", False):
                return  # http://trac.buildbot.net/ticket/3490#ticket
                # connection.execute('pragma foreign_keys=ON')

        sa.event.listen(engine.pool, 'connect', connect_listener_enable_fk)
        # try to enable WAL logging
        if u.database:
            def connect_listener(connection, record):
                connection.execute("pragma checkpoint_fullfsync = off")

            sa.event.listen(engine.pool, 'connect', connect_listener)

            log.msg("setting database journal mode to 'wal'")
            try:
                engine.execute("pragma journal_mode = wal")
            except Exception:
                log.msg("failed to set journal mode - database may fail")


class MySQLStrategy(Strategy):
    disconnect_error_codes = (2006, 2013, 2014, 2045, 2055)
    deadlock_error_codes = (1213,)

    def in_error_codes(self, args, error_codes):
        if args:
            return args[0] in error_codes
        return False

    def is_disconnect(self, args):
        return self.in_error_codes(args, self.disconnect_error_codes)

    def is_deadlock(self, args):
        return self.in_error_codes(args, self.deadlock_error_codes)

    def set_up(self, u, engine):
        """Special setup for mysql engines"""
        # add the reconnecting PoolListener that will detect a
        # disconnected connection and automatically start a new
        # one.  This provides a measure of additional safety over
        # the pool_recycle parameter, and is useful when e.g., the
        # mysql server goes away
        def checkout_listener(dbapi_con, con_record, con_proxy):
            try:
                cursor = dbapi_con.cursor()
                cursor.execute("SELECT 1")
            except dbapi_con.OperationalError as ex:
                if self.is_disconnect(ex.args):
                    # sqlalchemy will re-create the connection
                    log.msg('connection will be removed')
                    raise sa.exc.DisconnectionError()
                log.msg(f'exception happened {ex}')
                raise

        # older versions of sqlalchemy require the listener to be specified
        # in the kwargs, in a class instance
        if sautils.sa_version() < (0, 7, 0):
            class ReconnectingListener:
                pass
            rcl = ReconnectingListener()
            rcl.checkout = checkout_listener
            engine.pool.add_listener(rcl)
        else:
            sa.event.listen(engine.pool, 'checkout', checkout_listener)

    def should_retry(self, ex):
        return any([self.is_disconnect(ex.orig.args),
                    self.is_deadlock(ex.orig.args),
                    super().should_retry(ex)])


def sa_url_set_attr(u, attr, value):
    if hasattr(u, 'set'):
        return u.set(**{attr: value})
    setattr(u, attr, value)
    return u


def special_case_sqlite(u, kwargs):
    """For sqlite, percent-substitute %(basedir)s and use a full
    path to the basedir.  If using a memory database, force the
    pool size to be 1."""
    max_conns = 1

    # when given a database path, stick the basedir in there
    if u.database:

        # Use NullPool instead of the sqlalchemy-0.6.8-default
        # SingletonThreadPool for sqlite to suppress the error in
        # http://groups.google.com/group/sqlalchemy/msg/f8482e4721a89589,
        # which also explains that NullPool is the new default in
        # sqlalchemy 0.7 for non-memory SQLite databases.
        kwargs.setdefault('poolclass', NullPool)

        database = u.database
        database = database % dict(basedir=kwargs['basedir'])
        if not os.path.isabs(database[0]):
            database = os.path.join(kwargs['basedir'], database)

        u = sa_url_set_attr(u, 'database', database)

    else:
        # For in-memory database SQLAlchemy will use SingletonThreadPool
        # and we will run connection creation and all queries in the single
        # thread.
        # However connection destruction will be run from the main
        # thread, which is safe in our case, but not safe in general,
        # so SQLite will emit warning about it.
        # Silence that warning.
        kwargs.setdefault('connect_args', {})['check_same_thread'] = False

    # ignore serializing access to the db
    if 'serialize_access' in u.query:
        query = dict(u.query)
        query.pop('serialize_access')
        u = sa_url_set_attr(u, 'query', query)

    return u, kwargs, max_conns


def special_case_mysql(u, kwargs):
    """For mysql, take max_idle out of the query arguments, and
    use its value for pool_recycle.  Also, force use_unicode and
    charset to be True and 'utf8', failing if they were set to
    anything else."""
    query = dict(u.query)

    kwargs['pool_recycle'] = int(query.pop('max_idle', 3600))

    # default to the MyISAM storage engine
    storage_engine = query.pop('storage_engine', 'MyISAM')

    kwargs['connect_args'] = {
        'init_command': f'SET default_storage_engine={storage_engine}'
    }

    if 'use_unicode' in query:
        if query['use_unicode'] != "True":
            raise TypeError("Buildbot requires use_unicode=True " +
                            "(and adds it automatically)")
    else:
        query['use_unicode'] = "True"

    if 'charset' in query:
        if query['charset'] != "utf8":
            raise TypeError("Buildbot requires charset=utf8 " +
                            "(and adds it automatically)")
    else:
        query['charset'] = 'utf8'

    u = sa_url_set_attr(u, 'query', query)

    return u, kwargs, None


def get_drivers_strategy(drivername):
    if drivername.startswith('sqlite'):
        return SqlLiteStrategy()
    elif drivername.startswith('mysql'):
        return MySQLStrategy()
    return Strategy()


def create_engine(name_or_url, **kwargs):
    if 'basedir' not in kwargs:
        raise TypeError('no basedir supplied to create_engine')

    max_conns = None

    # apply special cases
    u = url.make_url(name_or_url)
    if u.drivername.startswith('sqlite'):
        u, kwargs, max_conns = special_case_sqlite(u, kwargs)
    elif u.drivername.startswith('mysql'):
        u, kwargs, max_conns = special_case_mysql(u, kwargs)

    # remove the basedir as it may confuse sqlalchemy
    basedir = kwargs.pop('basedir')

    # calculate the maximum number of connections from the pool parameters,
    # if it hasn't already been specified
    if max_conns is None:
        max_conns = kwargs.get(
            'pool_size', 5) + kwargs.get('max_overflow', 10)
    driver_strategy = get_drivers_strategy(u.drivername)
    engine = sa.create_engine(u, **kwargs)
    driver_strategy.set_up(u, engine)
    engine.should_retry = driver_strategy.should_retry
    # annotate the engine with the optimal thread pool size; this is used
    # by DBConnector to configure the surrounding thread pool
    engine.optimal_thread_pool_size = max_conns

    # keep the basedir
    engine.buildbot_basedir = basedir
    return engine
