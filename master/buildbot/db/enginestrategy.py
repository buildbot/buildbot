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
import re

import migrate
import sqlalchemy as sa
from sqlalchemy.engine import strategies
from sqlalchemy.engine import url
from sqlalchemy.pool import NullPool
from twisted.python import log

from buildbot.util import sautils


# from http://www.mail-archive.com/sqlalchemy@googlegroups.com/msg15079.html


class ReconnectingListener(object):

    def __init__(self):
        self.retried = False


def get_sqlalchemy_migrate_version():
    # sqlalchemy-migrate started including a version number in 0.7
    # Borrowed from model.py
    version = getattr(migrate, '__version__', 'old')
    if version == 'old':
        try:
            from migrate.versioning import schemadiff
            if hasattr(schemadiff, 'ColDiff'):
                version = "0.6.1"
            else:
                version = "0.6"
        except Exception:
            version = "0.0"
    return tuple(map(int, version.split('.')))


class BuildbotEngineStrategy(strategies.ThreadLocalEngineStrategy):
    # A subclass of the ThreadLocalEngineStrategy that can effectively interact
    # with Buildbot.
    #
    # This adjusts the passed-in parameters to ensure that we get the behaviors
    # Buildbot wants from particular drivers, and wraps the outgoing Engine
    # object so that its methods run in threads and return deferreds.

    name = 'buildbot'

    def special_case_sqlite(self, u, kwargs):
        """For sqlite, percent-substitute %(basedir)s and use a full
        path to the basedir.  If using a memory database, force the
        pool size to be 1."""
        max_conns = None

        # when given a database path, stick the basedir in there
        if u.database:

            # Use NullPool instead of the sqlalchemy-0.6.8-default
            # SingletonThreadPool for sqlite to suppress the error in
            # http://groups.google.com/group/sqlalchemy/msg/f8482e4721a89589,
            # which also explains that NullPool is the new default in
            # sqlalchemy 0.7 for non-memory SQLite databases.
            kwargs.setdefault('poolclass', NullPool)

            u.database = u.database % dict(basedir=kwargs['basedir'])
            if not os.path.isabs(u.database[0]):
                u.database = os.path.join(kwargs['basedir'], u.database)

        else:
            # For in-memory database SQLAlchemy will use SingletonThreadPool
            # and we will run connection creation and all queries in the single
            # thread.
            # However connection destruction will be run from the main
            # thread, which is safe in our case, but not safe in general,
            # so SQLite will emit warning about it.
            # Silence that warning.
            kwargs.setdefault('connect_args', {})['check_same_thread'] = False

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

    def special_case_mysql(self, u, kwargs):
        """For mysql, take max_idle out of the query arguments, and
        use its value for pool_recycle.  Also, force use_unicode and
        charset to be True and 'utf8', failing if they were set to
        anything else."""

        kwargs['pool_recycle'] = int(u.query.pop('max_idle', 3600))

        # default to the MyISAM storage engine
        storage_engine = u.query.pop('storage_engine', 'MyISAM')
        kwargs['connect_args'] = {
            'init_command': 'SET default_storage_engine=%s' % storage_engine,
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

        return u, kwargs, None

    def set_up_mysql_engine(self, u, engine):
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
                if ex.args[0] in (2006, 2013, 2014, 2045, 2055):
                    # sqlalchemy will re-create the connection
                    raise sa.exc.DisconnectionError()
                raise

        # older versions of sqlalchemy require the listener to be specified
        # in the kwargs, in a class instance
        if sautils.sa_version() < (0, 7, 0):
            class ReconnectingListener(object):
                pass
            rcl = ReconnectingListener()
            rcl.checkout = checkout_listener
            engine.pool.add_listener(rcl)
        else:
            sa.event.listen(engine.pool, 'checkout', checkout_listener)

    def check_sqlalchemy_version(self):
        version = getattr(sa, '__version__', '0')
        try:
            version_digits = re.sub('[^0-9.]', '', version)
            version_tup = tuple(map(int, version_digits.split('.')))
        except TypeError:
            return  # unparseable -- oh well

        if version_tup < (0, 6):
            raise RuntimeError("SQLAlchemy version %s is too old" % (version,))
        if version_tup > (0, 7, 10):
            mvt = get_sqlalchemy_migrate_version()
            if mvt < (0, 8, 0):
                raise RuntimeError("SQLAlchemy version %s is not supported by "
                                   "SQLAlchemy-Migrate version %d.%d.%d" % (version, mvt[0], mvt[1], mvt[2]))

    def create(self, name_or_url, **kwargs):
        if 'basedir' not in kwargs:
            raise TypeError('no basedir supplied to create_engine')
        self.check_sqlalchemy_version()

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
            max_conns = kwargs.get(
                'pool_size', 5) + kwargs.get('max_overflow', 10)

        engine = strategies.ThreadLocalEngineStrategy.create(self,
                                                             u, **kwargs)

        # annotate the engine with the optimal thread pool size; this is used
        # by DBConnector to configure the surrounding thread pool
        engine.optimal_thread_pool_size = max_conns

        # keep the basedir
        engine.buildbot_basedir = basedir

        if u.drivername.startswith('sqlite'):
            self.set_up_sqlite_engine(u, engine)
        elif u.drivername.startswith('mysql'):
            self.set_up_mysql_engine(u, engine)

        return engine

BuildbotEngineStrategy()

# this module is really imported for the side-effects, but pyflakes will like
# us to use something from the module -- so offer a copy of create_engine,
# which explicitly adds the strategy argument


def create_engine(*args, **kwargs):
    kwargs['strategy'] = 'buildbot'

    return sa.create_engine(*args, **kwargs)
