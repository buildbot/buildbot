"""
A wrapper around `sqlalchemy.create_engine` that handles all of the
special cases that Buildbot needs.  Those include:

 - pool_recycle for MySQL
 - %(basedir) substitution
 - optimal thread pool size calculation

"""

import sqlalchemy
from sqlalchemy.engine import strategies, url

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
            u.database = u.database % dict(basedir = kwargs['basedir'])
            # no os.path.join here - this is a URL and thus always contains '/'
            if u.database[0] != '/':
                u.database = "%s/%s" % (kwargs['basedir'], u.database)

        # in-memory databases need exactly one connection
        if not u.database:
            kwargs['pool_size'] = 1
            max_conns = 1

        return u, kwargs, max_conns

    def special_case_mysql(self, u, kwargs):
        """For mysql, take max_idle out of the query arguments, and
        use its value for pool_recycle.  Also, force use_unicode and
        charset to be True and 'utf8', failing if they were set to
        anything else."""

        kwargs['pool_recycle'] = int(u.query.pop('max_idle', 3600))

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

    def create(self, name_or_url, **kwargs):
        if 'basedir' not in kwargs:
            raise TypeError('no basedir supplied to create_engine')

        max_conns = None

        # apply special cases
        u = url.make_url(name_or_url)
        if u.drivername.startswith('sqlite'):
            u, kwargs, max_conns = self.special_case_sqlite(u, kwargs)
        elif u.drivername.startswith('mysql'):
            u, kwargs, max_conns = self.special_case_sqlite(u, kwargs)

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

        # and keep the basedir
        engine.buildbot_basedir = basedir

        return engine

BuildbotEngineStrategy()

# this module is really imported for the side-effects, but pyflakes will like
# us to use something from the module -- so offer a copy of create_engine, which
# explicitly adds the strategy argument
def create_engine(*args, **kwargs):
    kwargs['strategy'] = 'buildbot'
    return sqlalchemy.create_engine(*args, **kwargs)
