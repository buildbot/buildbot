Global Configuration
--------------------

The keys in this section affect the operations of the buildmaster globally.

.. bb:cfg:: db
.. bb:cfg:: db_url

.. _Database-Specification:

Database Specification
~~~~~~~~~~~~~~~~~~~~~~

Buildbot requires a connection to a database to maintain certain state information, such as tracking pending build requests.
In the default configuration Buildbot uses a file-based SQLite database, stored in the :file:`state.sqlite` file of the master's base directory.
Override this configuration with the :bb:cfg:`db_url` parameter.

Buildbot accepts a database configuration in a dictionary named ``db``.
All keys are optional::

    c['db'] = {
        'db_url' : 'sqlite:///state.sqlite',
    }

The ``db_url`` key indicates the database engine to use.
The format of this parameter is completely documented at http://www.sqlalchemy.org/docs/dialects/, but is generally of the form::

     "driver://[username:password@]host:port/database[?args]"

These parameters can be specified directly in the configuration dictionary, as ``c['db_url']`` and ``c['db_poll_interval']``, although this method is deprecated.

The following sections give additional information for particular database backends:

.. index:: SQLite

SQLite
++++++

For sqlite databases, since there is no host and port, relative paths are specified with ``sqlite:///`` and absolute paths with ``sqlite:////``.
Examples::

    c['db_url'] = "sqlite:///state.sqlite"

SQLite requires no special configuration.

If Buildbot produces "database is locked" exceptions, try adding ``serialize_access=1`` to the DB URL as a workaround::

    c['db_url'] = "sqlite:///state.sqlite?serialize_access=1"

and please file a bug at http://trac.buildbot.net.

.. index:: MySQL

MySQL
+++++

.. code-block:: python

   c['db_url'] = "mysql://user:pass@somehost.com/database_name?max_idle=300"

The ``max_idle`` argument for MySQL connections is unique to Buildbot, and should be set to something less than the ``wait_timeout`` configured for your server.
This controls the SQLAlchemy ``pool_recycle`` parameter, which defaults to no timeout.
Setting this parameter ensures that connections are closed and re-opened after the configured amount of idle time.
If you see errors such as ``_mysql_exceptions.OperationalError: (2006, 'MySQL server has gone away')``, this means your ``max_idle`` setting is probably too high.
``show global variables like 'wait_timeout';`` will show what the currently configured ``wait_timeout`` is on your MySQL server.

Buildbot requires ``use_unique=True`` and ``charset=utf8``, and will add them automatically, so they do not need to be specified in ``db_url``.

MySQL defaults to the MyISAM storage engine, but this can be overridden with the ``storage_engine`` URL argument.

Note that, because of InnoDB's extremely short key length limitations, it cannot be used to run Buildbot.
See http://bugs.mysql.com/bug.php?id=4541 for more information.

Buildbot uses temporary tables internally to manage large transactions.

MySQL has trouble doing replication with temporary tables, so if you are using a replicated MySQL installation, you may need to handle this situation carefully.
The MySQL documentation (http://dev.mysql.com/doc/refman/5.5/en/replication-features-temptables.html) recommends using ``--replicate-wild-ignore-table`` to ignore temporary
tables that should not be replicated.
All Buildbot temporary tables begin with ``bbtmp_``, so an option such as ``--replicate-wild-ignore-table=bbtmp_.*`` may help.

.. index:: Postgres

Postgres
++++++++

.. code-block:: python

    c['db_url'] = "postgresql://username@hostname/dbname"

PosgreSQL requires no special configuration.

.. bb:cfg:: mq

.. _MQ-Specification:

MQ Specification
~~~~~~~~~~~~~~~~

Buildbot uses a message-queueing system to handle communication within the
master.  Messages are used to indicate events within the master, and components
that are interested in those events arrange to receive them.

The message queueing implementation is configured as a dictionary in the ``mq``
option.  The ``type`` key describes the type of MQ implemetation to be used.
Note that the implementation type cannot be changed in a reconfig.

The available implemenetation types are described in the following sections.

Simple
++++++

.. code-block:: python

    c['mq'] = {
        'type' : 'simple',
        'debug' : False,
    }

This is the default MQ implementation.  Similar to SQLite, it has no additional
software dependencies, but does not support multi-master mode.

Note that this implementation also does not support message persistence across
a restart of the master.  For example, if a change is received, but the master
shuts down before the schedulers can create build requests for it, then those
schedulers will not be notified of the change when the master starts again.

The ``debug`` key, which defaults to False, can be used to enable logging of
every message produced on this master.

.. bb:cfg:: multiMaster

.. _Multi-master-mode:

Multi-master mode
~~~~~~~~~~~~~~~~~

Normally buildbot operates using a single master process that uses the configured database to save state.

It is possible to configure buildbot to have multiple master processes that share state in the same database.
This has been well tested using a MySQL database.
There are several benefits of Multi-master mode:

  * You can have large numbers of build slaves handling the same queue of build requests.
    A single master can only handle so many slaves (the number is based on a number of factors including type of builds, number of builds, and master and slave IO and CPU capacity--there is no fixed formula).
    By adding another master which shares the queue of build requests, you can attach more slaves to this additional master, and increase your build throughput.

  * You can shut one master down to do maintenance, and other masters will continue to do builds.

State that is shared in the database includes:

  * List of changes
  * Scheduler names and internal state
  * Build requests, including the builder name

Because of this shared state, you are strongly encouraged to:

  * Ensure that each named scheduler runs on only one master.
    If the same scheduler runs on multiple masters, it will trigger duplicate builds and may produce other undesirable behaviors.

  * Ensure builder names are unique for a given build factory implementation.
    You can have the same builder name configured on many masters, but if the build factories differ, you will get different results depending on which master claims the build.

One suggested configuration is to have one buildbot master configured with just the scheduler and change sources; and then other masters configured with just the builders.

To enable multi-master mode in this configuration, you will need to set the :bb:cfg:`multiMaster` option so that buildbot doesn't warn about missing schedulers or builders.

::

    # Enable multiMaster mode; disables warnings about unknown builders and
    # schedulers
    c['multiMaster'] = True
    # Check for new build requests every 60 seconds
    c['db'] = {
        'db_url' : 'mysql://...',
    }

.. bb:cfg:: buildbotURL
.. bb:cfg:: titleURL
.. bb:cfg:: title

Site Definitions
~~~~~~~~~~~~~~~~

Three basic settings describe the buildmaster in status reports::

    c['title'] = "Buildbot"
    c['titleURL'] = "http://buildbot.sourceforge.net/"

:bb:cfg:`title` is a short string that will appear at the top of this buildbot installation's home page (linked to the :bb:cfg:`titleURL`).

:bb:cfg:`titleURL` is a URL string that must end with a slash (``/``).
HTML status displays will show ``title`` as a link to :bb:cfg:`titleURL`.
This URL is often used to provide a link from buildbot HTML pages to your project's home page.

The :bb:cfg:`buildbotURL` string should point to the location where the buildbot's internal web server is visible.
This URL must end with a slash (``/``).

When status notices are sent to users (either by email or over IRC), :bb:cfg:`buildbotURL` will be used to create a URL to the specific build or problem that they are being notified about.
It will also be made available to queriers (over IRC) who want to find out where to get more information about this buildbot.

.. bb:cfg:: logCompressionLimit
.. bb:cfg:: logCompressionMethod
.. bb:cfg:: logMaxSize
.. bb:cfg:: logMaxTailSize
.. bb:cfg:: logEncoding

.. _Log-Encodings:

Log Handling
~~~~~~~~~~~~

::

    c['logCompressionLimit'] = 16384
    c['logCompressionMethod'] = 'gz'
    c['logMaxSize'] = 1024*1024 # 1M
    c['logMaxTailSize'] = 32768
    c['logEncoding'] = 'utf-8'

The :bb:cfg:`logCompressionLimit` enables compression of build logs on disk for logs that are bigger than the given size, or disables that completely if set to ``False``.
The default value is 4096, which should be a reasonable default on most file systems.
This setting has no impact on status plugins, and merely affects the required disk space on the master for build logs.

The :bb:cfg:`logCompressionMethod` controls what type of compression is used for build logs.
The default is 'bz2', and the other valid option is 'gz'.  'bz2' offers better compression at the expense of more CPU time.

The :bb:cfg:`logMaxSize` parameter sets an upper limit (in bytes) to how large logs from an individual build step can be.
The default value is None, meaning no upper limit to the log size.
Any output exceeding :bb:cfg:`logMaxSize` will be truncated, and a message to this effect will be added to the log's HEADER channel.

If :bb:cfg:`logMaxSize` is set, and the output from a step exceeds the maximum, the :bb:cfg:`logMaxTailSize` parameter controls how much of the end of the build log will be kept.
The effect of setting this parameter is that the log will contain the first :bb:cfg:`logMaxSize` bytes and the last :bb:cfg:`logMaxTailSize` bytes of output.
Don't set this value too high, as the the tail of the log is kept in memory.

The :bb:cfg:`logEncoding` parameter specifies the character encoding to use to decode bytestrings provided as logs.
It defaults to ``utf-8``, which should work in most cases, but can be overridden if necessary.
In extreme cases, a callable can be specified for this parameter.
It will be called with byte strings, and should return the corresponding Unicode string.

This setting can be overridden for a single build step with the ``logEncoding`` step parameter.
It can also be overridden for a single log file by passing the ``logEncoding`` parameter to :py:meth:`~buildbot.process.buildstep.addLog`.

Data Lifetime
~~~~~~~~~~~~~

.. bb:cfg:: changeHorizon
.. bb:cfg:: buildHorizon
.. bb:cfg:: eventHorizon
.. bb:cfg:: logHorizon

Horizons
++++++++

::

    c['changeHorizon'] = 200
    c['buildHorizon'] = 100
    c['eventHorizon'] = 50
    c['logHorizon'] = 40
    c['buildCacheSize'] = 15

Buildbot stores historical information on disk in the form of "Pickle" files and compressed logfiles.
In a large installation, these can quickly consume disk space, yet in many cases developers never consult this historical information.

The :bb:cfg:`changeHorizon` key determines how many changes the master will keep a record of. One place these changes are displayed is on the waterfall page.
This parameter defaults to 0, which means keep all changes indefinitely.

The :bb:cfg:`buildHorizon` specifies the minimum number of builds for each builder which should be kept on disk.
The :bb:cfg:`eventHorizon` specifies the minimum number of events to keep--events mostly describe connections and disconnections of slaves, and are seldom helpful to developers.
The :bb:cfg:`logHorizon` gives the minimum number of builds for which logs should be maintained; this parameter must be less than or equal to :bb:cfg:`buildHorizon`.
Builds older than :bb:cfg:`logHorizon` but not older than :bb:cfg:`buildHorizon` will maintain their overall status and the status of each step, but the logfiles will be deleted.

.. bb:cfg:: caches
.. bb:cfg:: changeCacheSize
.. bb:cfg:: buildCacheSize


Caches
++++++

::

    c['caches'] = {
        'Changes' : 100,     # formerly c['changeCacheSize']
        'Builds' : 500,      # formerly c['buildCacheSize']
        'chdicts' : 100,
        'BuildRequests' : 10,
        'SourceStamps' : 20,
        'ssdicts' : 20,
        'objectids' : 10,
        'usdicts' : 100,
    }

The :bb:cfg:`caches` configuration key contains the configuration for Buildbot's in-memory caches.
These caches keep frequently-used objects in memory to avoid unnecessary trips to the database or to pickle files.
Caches are divided by object type, and each has a configurable maximum size.

The default size for each cache is 1, except where noted below.
A value of 1 allows Buildbot to make a number of optimizations without consuming much memory.
Larger, busier installations will likely want to increase these values.

The available caches are:

``Changes``
    the number of change objects to cache in memory.
    This should be larger than the number of changes that typically arrive in the span of a few minutes, otherwise your schedulers will be reloading changes from the database every time they run.
    For distributed version control systems, like Git or Hg, several thousand changes may arrive at once, so setting this parameter to something like 10000 isn't unreasonable.

    This parameter is the same as the deprecated global parameter :bb:cfg:`changeCacheSize`.  Its default value is 10.

``Builds``
    The :bb:cfg:`buildCacheSize` parameter gives the number of builds for each builder which are cached in memory.
    This number should be larger than the number of builds required for commonly-used status displays (the waterfall or grid views), so that those displays do not miss the cache on a refresh.

    This parameter is the same as the deprecated global parameter :bb:cfg:`buildCacheSize`.  Its default value is 15.

``chdicts``
    The number of rows from the ``changes`` table to cache in memory.
    This value should be similar to the value for ``Changes``.

``BuildRequests``
    The number of BuildRequest objects kept in memory.
    This number should be higher than the typical number of outstanding build requests.
    If the master ordinarily finds jobs for BuildRequests immediately, you may set a lower value.

``SourceStamps``
   the number of SourceStamp objects kept in memory.
   This number should generally be similar to the number ``BuildRequesets``.

``ssdicts``
    The number of rows from the ``sourcestamps`` table to cache in memory.
    This value should be similar to the value for ``SourceStamps``.

``objectids``
    The number of object IDs - a means to correlate an object in the Buildbot configuration with an identity in the database--to cache.
    In this version, object IDs are not looked up often during runtime, so a relatively low value such as 10 is fine.

``usdicts``
    The number of rows from the ``users`` table to cache in memory.
    Note that for a given user there will be a row for each attribute that user has.

    c['buildCacheSize'] = 15

.. bb:cfg:: mergeRequests

.. index:: Builds; merging

Merging Build Requests
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   c['mergeRequests'] = True

This is a global default value for builders' :bb:cfg:`mergeRequests` parameter, and controls the merging of build requests.

This parameter can be overridden on a per-builder basis.
See :ref:`Merging-Build-Requests` for the allowed values for this parameter.

.. note::

    This feature is currently not working in buildbot nine. http://trac.buildbot.net/ticket/2645

.. index:: Builders; priority

.. bb:cfg:: prioritizeBuilders

.. _Prioritizing-Builders:

Prioritizing Builders
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def prioritizeBuilders(buildmaster, builders):
       ...
   c['prioritizeBuilders'] = prioritizeBuilders

By default, buildbot will attempt to start builds on builders in order, beginning with the builder with the oldest pending request.
Customize this behavior with the :bb:cfg:`prioritizeBuilders` configuration key, which takes a callable.
See :ref:`Builder-Priority-Functions` for details on this callable.

This parameter controls the order that the build master can start builds, and is useful in situations where there is resource contention between builders, e.g., for a test database.
It does not affect the order in which a builder processes the build requests in its queue.
For that purpose, see :ref:`Prioritizing-Builds`.

.. bb:cfg:: protocols

.. _Setting-the-PB-Port-for-Slaves:

Setting the PB Port for Slaves
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    c['protocols'] = {"pb": {"port": 10000}}

The buildmaster will listen on a TCP port of your choosing for connections from buildslaves.
It can also use this port for connections from remote Change Sources, status clients, and debug tools.
This port should be visible to the outside world, and you'll need to tell your buildslave admins about your choice.

It does not matter which port you pick, as long it is externally visible; however, you should probably use something larger than 1024, since most operating systems don't allow non-root processes to bind to low-numbered ports.
If your buildmaster is behind a firewall or a NAT box of some sort, you may have to configure your firewall to permit inbound connections to this port.

``c['protocols']['pb']['port']`` is a *strports* specification string, defined in the ``twisted.application.strports`` module (try ``pydoc twisted.application.strports`` to get documentation on the format).

This means that you can have the buildmaster listen on a localhost-only port by doing:

.. code-block:: python

   c['protocols'] = {"pb": {"port": "tcp:10000:interface=127.0.0.1"}}

This might be useful if you only run buildslaves on the same machine, and they are all configured to contact the buildmaster at ``localhost:10000``.

.. note:: In Buildbot versions <=0.8.8 you might see ``slavePortnum`` option.
   This option contains same value as ``c['protocols']['pb']['port']`` but not recomended to use.

.. index:: Properties; global

.. bb:cfg:: properties

Defining Global Properties
~~~~~~~~~~~~~~~~~~~~~~~~~~

The :bb:cfg:`properties` configuration key defines a dictionary of properties that will be available to all builds started by the buildmaster:

.. code-block:: python

   c['properties'] = {
       'Widget-version' : '1.2',
       'release-stage' : 'alpha'
   }

.. index:: Manhole

.. bb:cfg:: manhole

Manhole
~~~~~~~

If you set :bb:cfg:`manhole` to an instance of one of the classes in ``buildbot.manhole``, you can telnet or ssh into the buildmaster and get an interactive Python shell, which may be useful for debugging buildbot internals.
It is probably only useful for buildbot developers.
It exposes full access to the buildmaster's account (including the ability to modify and delete files), so it should not be enabled with a weak or easily guessable password.

There are three separate :class:`Manhole` classes.
Two of them use SSH, one uses unencrypted telnet.
Two of them use a username+password combination to grant access, one of them uses an SSH-style :file:`authorized_keys` file which contains a list of ssh public keys.

.. note:: Using any Manhole requires that ``pycrypto`` and ``pyasn1`` be installed.
   These are not part of the normal Buildbot dependencies.

`manhole.AuthorizedKeysManhole`
    You construct this with the name of a file that contains one SSH public key per line, just like :file:`~/.ssh/authorized_keys`.
    If you provide a non-absolute filename, it will be interpreted relative to the buildmaster's base directory.

`manhole.PasswordManhole`
    This one accepts SSH connections but asks for a username and password when authenticating.
    It accepts only one such pair.

`manhole.TelnetManhole`
    This accepts regular unencrypted telnet connections, and asks for a username/password pair before providing access.
    Because this username/password is transmitted in the clear, and because Manhole access to the buildmaster is equivalent to granting full shell privileges to both the buildmaster and all the buildslaves (and to all accounts which then run code produced by the buildslaves), it is  highly recommended that you use one of the SSH manholes instead.

::

    # some examples:
    from buildbot import manhole
    c['manhole'] = manhole.AuthorizedKeysManhole(1234, "authorized_keys")
    c['manhole'] = manhole.PasswordManhole(1234, "alice", "mysecretpassword")
    c['manhole'] = manhole.TelnetManhole(1234, "bob", "snoop_my_password_please")

The :class:`Manhole` instance can be configured to listen on a specific port.
You may wish to have this listening port bind to the loopback interface (sometimes known as `lo0`, `localhost`, or 127.0.0.1) to restrict access to clients which are running on the same host. ::

    from buildbot.manhole import PasswordManhole
    c['manhole'] = PasswordManhole("tcp:9999:interface=127.0.0.1","admin","passwd")

To have the :class:`Manhole` listen on all interfaces, use ``"tcp:9999"`` or simply 9999.
This port specification uses ``twisted.application.strports``, so you can make it listen on SSL or even UNIX-domain sockets if you want.

Note that using any :class:`Manhole` requires that the `TwistedConch`_ package be installed.

The buildmaster's SSH server will use a different host key than the normal sshd running on a typical unix host.
This will cause the ssh client to complain about a `host key mismatch`, because it does not realize there are two separate servers running on the same host.
To avoid this, use a clause like the following in your :file:`.ssh/config` file:

.. code-block:: none

    Host remotehost-buildbot
    HostName remotehost
    HostKeyAlias remotehost-buildbot
    Port 9999
    # use 'user' if you use PasswordManhole and your name is not 'admin'.
    # if you use AuthorizedKeysManhole, this probably doesn't matter.
    User admin

Using Manhole
+++++++++++++

After you have connected to a manhole instance, you will find yourself at a Python prompt.
You have access to two objects: ``master`` (the BuildMaster) and ``status`` (the master's Status object).
Most interesting objects on the master can be reached from these two objects.

To aid in navigation, the ``show`` method is defined.
It displays the non-method attributes of an object.

A manhole session might look like::

    >>> show(master)
    data attributes of <buildbot.master.BuildMaster instance at 0x7f7a4ab7df38>
                           basedir : '/home/dustin/code/buildbot/t/buildbot/'...
                         botmaster : <type 'instance'>
                    buildCacheSize : None
                      buildHorizon : None
                       buildbotURL : http://localhost:8010/
                   changeCacheSize : None
                        change_svc : <type 'instance'>
                    configFileName : master.cfg
                                db : <class 'buildbot.db.connector.DBConnector'>
                            db_url : sqlite:///state.sqlite
                                  ...
    >>> show(master.botmaster.builders['win32'])
    data attributes of <Builder ''builder'' at 48963528>
                                  ...
    >>> win32 = _
    >>> win32.category = 'w32'

.. bb:cfg:: metrics

Metrics Options
~~~~~~~~~~~~~~~

::

    c['metrics'] = dict(log_interval=10, periodic_interval=10)

:bb:cfg:`metrics` can be a dictionary that configures various aspects of the metrics subsystem.
If :bb:cfg:`metrics` is ``None``, then metrics collection, logging and reporting will be disabled.

``log_interval`` determines how often metrics should be logged to twistd.log.
It defaults to 60s.
If set to 0 or ``None``, then logging of metrics will be disabled.
This value can be changed via a reconfig.

``periodic_interval`` determines how often various non-event based metrics are collected, such as memory usage, uncollectable garbage, reactor delay.
This defaults to 10s.
If set to 0 or ``None``, then periodic collection of this data is disabled.
This value can also be changed via a reconfig.

Read more about metrics in the :ref:`Metrics` section in the developer documentation.

.. bb:cfg:: user_managers

.. _Users-Options:

Users Options
~~~~~~~~~~~~~

::

    from buildbot.process.users import manual
    c['user_managers'] = []
    c['user_managers'].append(manual.CommandlineUserManager(username="user",
                                                       passwd="userpw",
                                                       port=9990))

:bb:cfg:`user_managers` contains a list of ways to manually manage User Objects within Buildbot (see :ref:`User-Objects`).
Currently implemented is a commandline tool `buildbot user`, described at length in :bb:cmdline:`user`.
In the future, a web client will also be able to manage User Objects and their attributes.

As shown above, to enable the `buildbot user` tool, you must initialize a `CommandlineUserManager` instance in your `master.cfg`.
`CommandlineUserManager` instances require the following arguments:

``username``
    This is the `username` that will be registered on the PB connection and need to be used when calling `buildbot user`.

``passwd``
    This is the `passwd` that will be registered on the PB connection and need to be used when calling `buildbot user`.

``port``
    The PB connection `port` must be different than `c['protocols']['pb']['port']` and be specified when calling `buildbot user`

.. bb:cfg:: validation

.. _Input-Validation:

Input Validation
~~~~~~~~~~~~~~~~

::

    import re
    c['validation'] = {
        'branch' : re.compile(r'^[\w.+/~-]*$'),
        'revision' : re.compile(r'^[ \w\.\-\/]*$'),
        'property_name' : re.compile(r'^[\w\.\-\/\~:]*$'),
        'property_value' : re.compile(r'^[\w\.\-\/\~:]*$'),
    }

This option configures the validation applied to user inputs of various types.
This validation is important since these values are often included in command-line arguments executed on slaves.
Allowing arbitrary input from untrusted users may raise security concerns.

The keys describe the type of input validated; the values are compiled regular expressions against which the input will be matched.
The defaults for each type of input are those given in the example, above.

.. bb:cfg:: revlink

Revision Links
~~~~~~~~~~~~~~

The :bb:cfg:`revlink` parameter is used to create links from revision IDs in the web status to a web-view of your source control system.
The parameter's value must be a callable.

By default, Buildbot is configured to generate revlinks for a number of open source hosting platforms.

The callable takes the revision id and repository argument, and should return an URL to the revision.
Note that the revision id may not always be in the form you expect, so code defensively.
In particular, a revision of "??" may be supplied when no other information is available.

Note that :class:`SourceStamp`\s that are not created from version-control changes (e.g., those created by a Nightly or Periodic scheduler) may have an empty repository string, if the repository is not known to the scheduler.

Revision Link Helpers
+++++++++++++++++++++

Buildbot provides two helpers for generating revision links.
:class:`buildbot.revlinks.RevlinkMatcher` takes a list of regular expressions, and replacement text.
The regular expressions should all have the same number of capture groups.
The replacement text should have sed-style references to that capture groups (i.e. '\1' for the first capture group), and a single '%s' reference, for the revision ID.
The repository given is tried against each regular expression in turn.
The results are the substituted into the replacement text, along with the revision ID to obtain the revision link.

::

        from buildbot import revlinks
        c['revlink'] = revlinks.RevlinkMatch([r'git://notmuchmail.org/git/(.*)'],
                                              r'http://git.notmuchmail.org/git/\1/commit/%s')

:class:`buildbot.revlinks.RevlinkMultiplexer` takes a list of revision link callables, and tries each in turn, returning the first successful match.

.. bb:cfg:: www

Web Server
~~~~~~~~~~

Buildbot contains a built-in web server.
This server is configured with the :bb:cfg:`www` configuration key, which specifies a dictionary with the following keys:

.. note:
    As of Buildbot 0.9.0, the built-in web server replaces the old ``WebStatus`` plugin.

``port``
    The TCP port on which to serve requests.
    Note that SSL is not supported.
    To host Buildbot with SSL, use an HTTP proxy such as lighttpd, nginx, or Apache.
    If this is ``None``, the default, then the master will not implement a web server.

``url``
    The URL of the buildbot web server.
    This value is used to generate URLs throughout Buildbot, and should take into account any translations performed by HTTP proxies.

    Note that this parameter need not point to this master.
    For example, in a configuration with a master devoted to web service and a master devoted to scheduling and running builds, both should be configured with the same ``url``.
    Then any strings that are generated by status plugins such as IRC or MailNotifier will contain working URLs.

    The default URL is ``http://localhost:8080``, or on ``port`` if it is specified.
    This is probably not what you want!

``json_cache_seconds``
    The number of seconds into the future at which an HTTP API response should expire.
    Any versions less than this value will not be available.
    This can be used to ensure that no clients are depending on API versions that will soon be removed from Buildbot.

``rest_minimum_version``
    The minimum supported REST API version.
    Any versions less than this value will not be available.
    This can be used to ensure that no clients are depending on API versions that will soon be removed from Buildbot.

``plugins``
    This key gives a dictionary of additional UI plugins to load, along with configuration for those plugins.
    These plugins must be separately installed in the Python environment, e.g., ``pip install buildbot-www-waterfall``.
    For example ::

        c['www'] = {
            'plugins': {'waterfall': {'num_builds': 50}}
        }

``debug``
    If true, then debugging information will be output to the browser.
    This is best set to false (the default) on production systems, to avoid the possibility of information leakage.

``allowed_origins``
    This gives a list of origins which are allowed to access the Buildbot API (including control via JSONRPC 2.0).
    It implements cross-origin request sharing (CORS), allowing pages at origins other than the Buildbot UI to use the API.
    Each origin is interpreted as filename match expression, with ``?`` matching one character and ``*`` matching anything.
    Thus ``['*']`` will match all origins, and ``['https://*.buildbot.net']`` will match secure sites under ``buildbot.net``.
    The Buildbot UI will operate correctly without this parameter; it is only useful for allowing access from other web applications.

``auth``
   Authentication module to use for the web server. See :bb:cfg:`auth`

``avatar_methods``
    List of methods that can be used to get avatar pictures to use for the web server.
    By default, buildbot uses Gravatar to get images associated with each users, if you want to disable this you can just specify empty list::

        c['www'] = {
            'avatar_methods': []
        }

    For use of corporate pictures, you can use LdapUserInfos, which can also acts as an avatar provider.  See :bb:cfg:`auth`

.. bb:cfg:: auth

Authentication plugins
~~~~~~~~~~~~~~~~~~~~~~

By default, buildbot does not require people to authenticate in order to see the readonly data.
In order to access control feature in the web UI, you will need to configure an authentication plugin.

.. py:class:: buildbot.auth.NoAuth

    This class is the default authentication plugin, which disables authentication

.. py:class:: buildbot.auth.BasicAuth

    This class implements a basic authentication mechanism using a list of user/password tuples provided from the configuration file.

    * ``users``: list of ``("user","password")`` tuples, or dictionary ``dict(user="passwd")``

    example::

        from buildbot.auth import BasicAuth
        auth=BasicAuth({"homer": "doh!"})

.. py:class:: buildbot.auth.HTPasswdAuth

    This class implements an authentication against a standard :file:`.htpasswd` file.

    * ``passwdFile``: ``.htpasswd`` file to read

    example::

        from buildbot.auth import HTPasswdAuth
        auth=HTPasswdAuth("my_htpasswd")

.. py:class:: buildbot.oauth2.GoogleAuth

    This class implements an authentication with Google_ single sign-on.
    You can look at the Google_ oauth2 documentation on how to register your buildbot to the Google systems. The developer console will give you the two parameters you have to give to ``GoogleAuth``

    Please make sure you register your application with the ``BUILDBOT_URL/login`` url as the allowed redirect URIs.

    * ``clientId``: The client ID of your buildbot application

    * ``clientSecret``: The client secret of your buildbot application

    example::

        from buildbot.oauth2 import GoogleAuth
        auth=GoogleAuth("clientid", "clientsecret")

    in order to use this module, you need to install the python ``sanction`` module

    .. code-block:: bash

            pip install sanction

.. _Google: https://developers.google.com/accounts/docs/OAuth2

.. py:class:: buildbot.oauth2.GitHubAuth

    This class implements an authentication with GitHub_ single sign-on.
    You can look at the GitHub_ oauth2 documentation on how to register your buildbot to the GitHub systems. The developer console will give you the two parameters you have to give to ``GitHubAuth``

    Please make sure you register your application with the ``BUILDBOT_URL/login`` url as the allowed redirect URIs.

    * ``clientId``: The client ID of your buildbot application

    * ``clientSecret``: The client secret of your buildbot application

    example::

        from buildbot.oauth2 import GitHubAuth
        auth=GitHubAuth("clientid", "clientsecret")

    in order to use this module, you need to install the python ``sanction`` module

    .. code-block:: bash

            pip install sanction

.. _GitHub: http://developer.github.com/v3/oauth_authorizations/

.. py:class:: buildbot.auth.RemoteUserAuth

    In case if buildbot web ui is served through reverse proxy that supports HTTP-based authentication (like apache, lighttpd), it's possible to to tell buildbot to trust web server and get username from request headers.

    Administrator must make sure that it's impossible to get access to buildbot using other way than through frontend. Usually this means that buildbot should listen for incoming connections only on localhost (or on some firewall-protected port). Frontend must require HTTP authentication to access buildbot pages (using any source for credentials, such as htpasswd, PAM, LDAP, Kerberos).

    * ``header``: header to use to get the username (defaults to ``REMOTE_USER``)
    * ``headerRegex``: regular expression to get the username from header value. (defaults to ``"(?P<username>[^ @]+)@(?P<realm>[^ @]+)"). Note that your at least need to specify a ``?P<username>`` regular expression named group.

    example::

        from buildbot.auth import RemoteUserAuth
        auth=RemoteUserAuth()

    A corresponding Apache configuration example

     .. code-block:: none

        <Location "/">
                AuthType Kerberos
                AuthName "Buildbot login via Kerberos"
                KrbMethodNegotiate On
                KrbMethodK5Passwd On
                KrbAuthRealms <<YOUR CORP REALMS>>
                KrbVerifyKDC off
                KrbServiceName Any
                Krb5KeyTab /etc/krb5/krb5.keytab
                KrbSaveCredentials Off
                require valid-user
                Order allow,deny

                Satisfy Any

                #] SSO
                RewriteEngine On
                RewriteCond %{LA-U:REMOTE_USER} (.+)$
                RewriteRule . - [E=RU:%1,NS]
                RequestHeader set REMOTE_USER %{RU}e

        </Location>

    The advantage of http auth is that it is uses a proven and fast implementation for authentication. The problem is that the only information that is passed is the username, and there is no way to pass any other information like user email, user groups, etc.
    Those information can be very useful to the mailstatus plugin, or the authorization criterias.

    In order to get additional information, you can specify a :py:class:`buildbot.auth.UserInfosBase` object, which is responsible of getting more information about the user using any means. the :py:class:`buildbot.auth.UserInfosBase` has one method:

    .. py:method:: getUserInfos(username)

    Get additional info for one user. returns a :py:class:`dict` with following keys:

        * ``email``: email address of the user
        * ``full_name``: Full name of the user, like "Homer Simpson"
        * ``groups``: groups the user belongs to, like ["duff fans", "dads"]

    Following are the implemented sub classes of :py:class:`UserInfosBase`

.. py:class:: buildbot.ldapuserinfos.LdapUserInfos

        * ``uri``: uri of the ldap server
        * ``bind_user``: username of the ldap account that is used to get the infos for other users (usually a "faceless" account)
        * ``bind_pw``: password of the ``bind_user``
        * ``accountBase``: the base dn (distinguished name)of the user database
        * ``groupBase``: the base dn of the groups database
        * ``accountPattern``: the pattern for searching in the account database. This must contain the ``%(username)s`` string, which is replaced by the searched username
        * ``groupMemberPattern``: the pattern for searching in the group database. This must contain the ``%(dn)s`` string, which is replaced by the searched username's dn
        * ``accountFullName``: the name of the field in account ldap database where the full user name is to be found.
        * ``accountEmail``: the name of the field in account ldap database where the user email is to be found.
        * ``groupName``: the name of the field in groups ldap database where the group name is to be found.
        * ``avatarPattern``: the pattern for searching avatars from emails in the account database. This must contain the ``%(email)s`` string, which is replaced by the searched email
        * ``avatarData``: the name of the field in groups ldap database where the avatar picture is to be found. This field is supposed to contain the raw picture, format is automatically detected from jpeg, png or git.
        * ``accountExtraFields``: extra fields to extracts for use with the authorization policies.

        Example::

            from buildbot.www.auth import RemoteUserAuth
            from buildbot.www.ldapuserinfos import LdapUserInfos
            from buildbot.www.avatar import AvatarGravatar

            # this configuration works for MS Active Directory ldap implementation
            # we use it for user info, and avatars
            userInfos = LdapUserInfos(
                uri='ldap://ldap.mycompany.com:3268',
                bind_user='ldap_user',
                bind_pw='p4$$wd',
                accountBase='dc=corp,dc=mycompany,dc=com',
                groupBase='dc=corp,dc=mycompany,dc=com',
                accountPattern='(&(objectClass=person)(sAMAccountName=%(username)s))',
                accountFullName='displayName',
                accountEmail='mail',
                groupMemberPattern='(&(objectClass=group)(member=%(dn)s))',
                groupName='cn',
                avatarPattern='(&(objectClass=person)(mail=%(email)s))',
                avatarData='thumbnailPhoto',
            )
            c['www'] = dict(port=PORT, allowed_origins=["*"],
                            url=c['buildbotURL'],
                            auth=RemoteUserAuth(userInfos=userInfos),
                            avatar_methods=[userInfos, AvatarGravatar()]
                            )

        in order to use this module, you need to install the python ``ldap`` module

        .. code-block:: bash

                # its not a pure python, so you need to install some c library dependancies
                sudo apt-get builddep python-ldap
                pip install python-ldap


.. bb:cfg:: codebaseGenerator

Codebase Generator
~~~~~~~~~~~~~~~~~~

::

    all_repositories = {
        r'https://hg/hg/mailsuite/mailclient': 'mailexe',
        r'https://hg/hg/mailsuite/mapilib': 'mapilib',
        r'https://hg/hg/mailsuite/imaplib': 'imaplib',
        r'https://github.com/mailinc/mailsuite/mailclient': 'mailexe',
        r'https://github.com/mailinc/mailsuite/mapilib': 'mapilib',
        r'https://github.com/mailinc/mailsuite/imaplib': 'imaplib',
    }

    def codebaseGenerator(chdict):
        return all_repositories[chdict['repository']]

    c['codebaseGenerator'] = codebaseGenerator

For any incoming change, the :ref:`codebase<Attr-Codebase>` is set to ''.
This codebase value is sufficient if all changes come from the same repository (or clones).
If changes come from different repositories, extra processing will be needed to determine the codebase for the incoming change.
This codebase will then be a logical name for the combination of repository and or branch etc.

The `codebaseGenerator` accepts a change dictionary as produced by the :py:class:`buildbot.db.changes.ChangesConnectorComponent <changes connector component>`, with a changeid equal to `None`.

.. _TwistedConch: http://twistedmatrix.com/trac/wiki/TwistedConch

