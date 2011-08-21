.. -*- rst -*-
.. _Global-Configuration-global:

Global Configuration
--------------------

The keys in this section affect the operations of the buildmaster globally.

.. _Database-Specification:

Database Specification
~~~~~~~~~~~~~~~~~~~~~~

Buildbot requires a connection to a database to maintain certain state
information, such as tracking pending build requests.  By default this is
stored in a sqlite file called :file:`state.sqlite` in the base directory of your
master.  This can be overridden with the ``db_url`` parameter.

The format of this parameter is completely documented at
http://www.sqlalchemy.org/docs/dialects/, but is generally of the form:

.. code-block:: none

    driver://[username:password@]host:port/database[?args]

For sqlite databases, since there is no host and port, relative paths are
specified with ``sqlite:///`` and absolute paths with ``sqlite:////``.
Examples:

Notes for particular database backends:

SQLite
++++++

.. code-block:: python

    c['db_url'] = "sqlite:///state.sqlite"

No special configuration is required to use SQLite.

If you have trouble with "database is locked" exceptions, try adding
``serialize_access=1`` to the DB URL as a workaround::

    c['db_url'] = "sqlite:///state.sqlite?serialize_access=1"

and please file a bug at http://trac.buildbot.net.

MySQL
+++++

.. code-block:: python

    c['db_url'] = "mysql://user:pass@somehost.com/database_name?max_idle=300"


The ``max_idle`` argument for MySQL connections is unique to Buildbot, and
should be set to something less than the ``wait_timeout`` configured for your
server.  This controls the SQLAlchemy ``pool_recycle`` parameter, which
defaults to no timeout.  Setting this parameter ensures that connections are
closed and re-opened after the configured amount of idle time.  If you see
errors such as ``_mysql_exceptions.OperationalError: (2006, 'MySQL server
has gone away')``, this means your ``max_idle`` setting is probably too high.
``show global variables like 'wait_timeout';`` will show what the currently
configured ``wait_timeout`` is on your MySQL server.

Buildbot requires ``use_unique=True`` and ``charset=utf8``, and will add
them automatically, so they do not need to be specified in ``db_url``.

MySQL defaults to the MyISAM storage engine, but this can be overridden with
the ``storage_engine`` URL argument.  Note that, because of InnoDB's
extremely short key length limitations, it cannot be used to run Buildbot.  See
http://bugs.mysql.com/bug.php?id=4541 for more information.

Buildbot uses temporary tables internally to manage large transactions.  MySQL
has trouble doing replication with temporary tables, so if you are using a
replicated MySQL installation, you may need to handle this situation carefully.
The MySQL documentation
(http://dev.mysql.com/doc/refman/5.5/en/replication-features-temptables.html)
recommends using ``--replicate-wild-ignore-table`` to ignore temporary
tables that should not be replicated.  All Buildbot temporary tables begin with
``bbtmp_``, so an option such as
``--replicate-wild-ignore-table=bbtmp_.*`` may help.

Postgres
++++++++

.. code-block:: python

    c['db_url'] = "postgresql://username@@hostname/dbname"

No special configuration is required to use Postgres.

.. _Multi-master-mode:

Multi-master mode
~~~~~~~~~~~~~~~~~

Normally buildbot operates using a single master process that uses the
configured database to save state.

It is possible to configure buildbot to have multiple master processes that
share state in the same database. This has been well tested using a MySQL
database. There are several benefits of Multi-master mode:

  * You can have large numbers of build slaves handling the same queue of build
    requests.A single master can only handle so many slaves (the
    number is based on a number of factors including type of builds,
    number of builds, and master and slave IO and CPU capacity - there
    is no fixed formula).  By adding another master which shares the
    queue of build requests, you can attach more slaves to this
    additional master, and increase your build throughput.
        
  * You can shut one master down to do maintenance, and other masters will continue
    to do builds. 

State that is shared in the database includes:

  * List of changes
  * Scheduler names and internal state
  * Build requests, including the builder name 

Because of this shared state, you are strongly encouraged to:

  * Ensure that each named scheduler runs on only one master.  If the
    same scheduler runs on multiple masters, it will trigger duplicate
    builds and may produce other undesirable behaviors.

  * Ensure builder names are unique for a given build factory implementation. You
    can have the same builder name configured on many masters, but if the build
    factories differ, you will get different results depending on which master
    claims the build. 

One suggested configuration is to have one buildbot master configured with just
the scheduler and change sources; and then other masters configured with just
the builders.

To enable multi-master mode in this configuration, you will need to set the
``multiMaster`` option so that buildbot doesn't warn about missing schedulers or
builders. You will also need to set ``db_poll_interval`` to the masters with only
builders check the database for new build requests at the configured interval. ::

    # Enable multiMaster mode; disables warnings about unknown builders and
    # schedulers
    c['multiMaster'] = True
    # Check for new build requests every 60 seconds
    c['db_poll_interval'] = 60

.. _Site-Definitions:

Site Definitions
~~~~~~~~~~~~~~~~~~~

Three basic settings describe the buildmaster in status reports. ::

    c['title'] = "Buildbot"
    c['titleURL'] = "http://buildbot.sourceforge.net/"
    c['buildbotURL'] = "http://localhost:8010/"

.. index:: c['title']

``title`` is a short string that will appear at the top of this
buildbot installation's :class:`html.WebStatus` home page (linked to the
``titleURL``), and is embedded in the title of the waterfall HTML
page.

.. index:: c['titleURL']

``titleURL`` is a URL string that must end with a slash (``/``).
HTML status displays will show ``title`` as a link to
``titleURL``.  This URL is often used to provide a link from
buildbot HTML pages to your project's home page.

.. index:: c['buildbotURL']

The ``buildbotURL`` string should point to the location where the buildbot's
internal web server is visible. This URL must end with a slash (``/``).
This typically uses the port number set for the web status (:ref:`WebStatus`):
the buildbot needs your help to figure out a suitable externally-visible host
URL.


When status notices are sent to users (either by email or over IRC),
``buildbotURL`` will be used to create a URL to the specific build
or problem that they are being notified about. It will also be made
available to queriers (over IRC) who want to find out where to get
more information about this buildbot.

.. _Log-Handling:

Log Handling
~~~~~~~~~~~~

::

    c['logCompressionLimit'] = 16384
    c['logCompressionMethod'] = 'gz'
    c['logMaxSize'] = 1024*1024 # 1M
    c['logMaxTailSize'] = 32768

.. index::
   logCompressionLimit
   BuildMaster Config; logCompressionLimit

The ``logCompressionLimit`` enables compression of build logs on
disk for logs that are bigger than the given size, or disables that
completely if set to ``False``. The default value is 4k, which should
be a reasonable default on most file systems. This setting has no impact
on status plugins, and merely affects the required disk space on the
master for build logs.

.. index::
   logCompressionMethod
   BuildMaster Config; logCompressionMethod

The ``logCompressionMethod`` controls what type of compression is used for
build logs.  The default is 'bz2', the other valid option is 'gz'.  'bz2'
offers better compression at the expense of more CPU time.

.. index::
   logMaxSize
   BuildMaster Config; logMaxSize

The ``logMaxSize`` parameter sets an upper limit (in bytes) to how large
logs from an individual build step can be.  The default value is None, meaning
no upper limit to the log size.  Any output exceeding ``logMaxSize`` will be
truncated, and a message to this effect will be added to the log's HEADER
channel.

.. index::
   logMaxTailSize
   BuildMaster Config; logMaxTailSize

If ``logMaxSize`` is set, and the output from a step exceeds the maximum,
the ``logMaxTailSize`` parameter controls how much of the end of the build
log will be kept.  The effect of setting this parameter is that the log will
contain the first ``logMaxSize`` bytes and the last ``logMaxTailSize``
bytes of output.  Don't set this value too high, as the the tail of the log is
kept in memory.

.. _Data-Lifetime:

.. index::
   logHorizon, buildCacheSize, changeHorizon, buildHorizon, eventHorizon
   BuildMaster Config; logHorizon
   BuildMaster Config; buildCacheSize
   BuildMaster Config; changeHorizon
   BuildMaster Config; buildHorizon
   BuildMaster Config; eventHorizon

Data Lifetime
~~~~~~~~~~~~~

::

    c['changeHorizon'] = 200
    c['buildHorizon'] = 100
    c['eventHorizon'] = 50
    c['logHorizon'] = 40
    c['buildCacheSize'] = 15

Horizons
++++++++

Buildbot stores historical information on disk in the form of "Pickle" files
and compressed logfiles.  In a large installation, these can quickly consume
disk space, yet in many cases developers never consult this historical
information.  

The ``c['changeHorizon']`` key determines how many changes the master will
keep a record of. One place these changes are displayed is on the waterfall
page.  This parameter defaults to 0, which means keep all changes indefinitely.

The ``buildHorizon`` specifies the minimum number of builds for each builder
which should be kept on disk.  The ``eventHorizon`` specifies the minumum
number of events to keep -- events mostly describe connections and
disconnections of slaves, and are seldom helpful to developers.  The
``logHorizon`` gives the minimum number of builds for which logs should be
maintained; this parameter must be less than ``buildHorizon``. Builds older
than ``logHorizon`` but not older than ``buildHorizon`` will maintain
their overall status and the status of each step, but the logfiles will be
deleted.

Caches
++++++

The ``caches`` configuration key contains the configuration for Buildbot's
in-memory caches.  These caches keep frequently-used objects in memory to avoid
unnecessary trips to the database or to pickle files.  Caches are divided by
object type, and each has a configurable maximum size.  The default size for
each cache is 1, which allows Buildbot to make a number of optimizations
without consuming much memory.  Larger, busier installations will likely want
to increase these values.

The available caches are:

``Changes``
    the number of change objects to cache in memory.  This should be larger than
    the number of changes that typically arrive in the span of a few minutes,
    otherwise your schedulers will be reloading changes from the database every
    time they run.  For distributed version control systems, like git or hg,
    several thousand changes may arrive at once, so setting this parameter to
    something like 10000 isn't unreasonable.

    This parameter is the same as the deprecated global parameter
    ``changeCacheSize``.

``chdicts``
    The number of rows from the ``changes`` table to cache in memory.  This
    value should be similar to the value for ``Changes``.

``BuildRequests``
    the number of BuildRequest objects kept in memory.  This number should be
    higher than the typical number of outstanding build requests.  If the master
    ordinarily finds jobs for BuildRequests immediately, it can be set to a
    relatively low value.

``SourceStamps``
   the number of SourceStamp objects kept in memory.  This number
   should generally be similar to the number ``BuildRequesets``.

``ssdicts``
    The number of rows from the ``sourcestamps`` table to cache in memory.  This
    value should be similar to the value for ``SourceStamps``.

``objectids``
    The number of object IDs - a means to correlate an object in the
    Buildbot configuration with an identity in the database - to
    cache.  In this version, object IDs are not looked up often during
    runtime, so a relatively low value such as 10 is fine.

``usdicts``
    The number of rows from the ``users`` table to cache in memory.  Note that for
    a given user there will be a row for each attribute that user has.

The *global* ``buildCacheSize`` parameter gives the number of builds
for each builder which are cached in memory.  This number should be larger than
the number of builds required for commonly-used status displays (the waterfall
or grid views), so that those displays do not miss the cache on a
refresh. ::

    c['buildCacheSize'] = 15

.. _Merging-Build-Requests-Global:

.. index:: BuildMaster Config; mergeRequests

Merging Build Requests (global)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a global default value for builders' ``mergeRequests`` parameter,
and controls the merging of build requests.  See :ref:`Merging-Build-Requests`
for more details.

.. index::
   prioritizeBuilders
   BuildMaster Config; prioritizeBuilders

.. _Prioritizing-Builders:
    
Prioritizing Builders
~~~~~~~~~~~~~~~~~~~~~

By default, buildbot will attempt to start builds on builders in order from the
builder with the highest priority or oldest pending requst to the
lowest priority, newest request. This behaviour can be
customized with the ``c['prioritizeBuilders']`` configuration key.
This key specifies a function which is called with two arguments: a
``BuildMaster`` and a list of :class:`Builder` objects. It
should return a list of :class:`Builder` objects in the desired order.
It may also remove items from the list if builds should not be started
on those builders. If necessary, this function can return its
results via a Deferred (it is called with ``maybeDeferred``).

This parameter controls the order in which builders are activated.  It does not
affect the order in which a builder processes the build requests in its queue.
For that purpose, see :ref:`Prioritizing-Builds`. ::

    def prioritizeBuilders(buildmaster, builders):
        """Prioritize builders.  'finalRelease' builds have the highest
        priority, so they should be built before running tests, or
        creating builds."""
        builderPriorities = {
            "finalRelease": 0,
            "test": 1,
            "build": 2,
        }
        builders.sort(key=lambda b: builderPriorities.get(b.name, 0))
        return builders
    
    c['prioritizeBuilders'] = prioritizeBuilders

.. index::
   slavePortnum
   BuildMaster Config; slavePortnum

.. _Setting-the-PB-Port-for-Slaves:

Setting the PB Port for Slaves
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    c['slavePortnum'] = 10000

The buildmaster will listen on a TCP port of your choosing for
connections from buildslaves. It can also use this port for
connections from remote Change Sources, status clients, and debug
tools. This port should be visible to the outside world, and you'll
need to tell your buildslave admins about your choice.

It does not matter which port you pick, as long it is externally
visible, however you should probably use something larger than 1024,
since most operating systems don't allow non-root processes to bind to
low-numbered ports. If your buildmaster is behind a firewall or a NAT
box of some sort, you may have to configure your firewall to permit
inbound connections to this port.

``c['slavePortnum']`` is a *strports* specification string,
defined in the ``twisted.application.strports`` module (try
``pydoc twisted.application.strports`` to get documentation on
the format). This means that you can have the buildmaster listen on a
localhost-only port by doing::

    c['slavePortnum'] = "tcp:10000:interface=127.0.0.1"

This might be useful if you only run buildslaves on the same machine,
and they are all configured to contact the buildmaster at
``localhost:10000``.

.. _Defining-Global-Properties:

.. index::
   properties
   BuildMaster Config; properties

Defining Global Properties
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``'properties'`` configuration key defines a dictionary
of properties that will be available to all builds started by the
buildmaster::

    c['properties'] = {
        'Widget-version' : '1.2',
        'release-stage' : 'alpha'
    }

.. index::
   debugPassword
   BuildMaster Config; debugPassword

.. _Debug-Options:
    
Debug Options
~~~~~~~~~~~~~

If you set ``c['debugPassword']``, then you can connect to the
buildmaster with the diagnostic tool launched by :samp:`buildbot
debugclient {MASTER}:{PORT}`. From this tool, you can reload the config
file, manually force builds, and inject changes, which may be useful
for testing your buildmaster without actually commiting changes to
your repository (or before you have the Change Sources set up). The
debug tool uses the same port number as the slaves do:
``c['slavePortnum']``, and is authenticated with this password. ::

    c['debugPassword'] = "debugpassword"

.. index::
   manhole
   BuildMaster Config; manhole

Manhole
~~~~~~~

If you set ``c['manhole']`` to an instance of one of the classes in
``buildbot.manhole``, you can telnet or ssh into the buildmaster
and get an interactive Python shell, which may be useful for debugging
buildbot internals. It is probably only useful for buildbot
developers. It exposes full access to the buildmaster's account
(including the ability to modify and delete files), so it should not
be enabled with a weak or easily guessable password.

There are three separate :class:`Manhole` classes. Two of them use SSH,
one uses unencrypted telnet. Two of them use a username+password
combination to grant access, one of them uses an SSH-style
:file:`authorized_keys` file which contains a list of ssh public keys.

.. note:: Using any Manhole requires that ``pycrypto`` and
   ``pyasn1`` be installed.  These are not part of the normal Buildbot
   dependencies.

`manhole.AuthorizedKeysManhole`
    You construct this with the name of a file that contains one SSH
    public key per line, just like :file:`~/.ssh/authorized_keys`. If you
    provide a non-absolute filename, it will be interpreted relative to
    the buildmaster's base directory.

`manhole.PasswordManhole`
    This one accepts SSH connections but asks for a username and password
    when authenticating. It accepts only one such pair.


`manhole.TelnetManhole`
    This accepts regular unencrypted telnet connections, and asks for a
    username/password pair before providing access. Because this
    username/password is transmitted in the clear, and because Manhole
    access to the buildmaster is equivalent to granting full shell
    privileges to both the buildmaster and all the buildslaves (and to all
    accounts which then run code produced by the buildslaves), it is
    highly recommended that you use one of the SSH manholes instead.
    
::
    
    # some examples:
    from buildbot import manhole
    c['manhole'] = manhole.AuthorizedKeysManhole(1234, "authorized_keys")
    c['manhole'] = manhole.PasswordManhole(1234, "alice", "mysecretpassword")
    c['manhole'] = manhole.TelnetManhole(1234, "bob", "snoop_my_password_please")

The :class:`Manhole` instance can be configured to listen on a specific
port. You may wish to have this listening port bind to the loopback
interface (sometimes known as `lo0`, `localhost`, or 127.0.0.1) to
restrict access to clients which are running on the same host. ::

    from buildbot.manhole import PasswordManhole
    c['manhole'] = PasswordManhole("tcp:9999:interface=127.0.0.1","admin","passwd")

To have the :class:`Manhole` listen on all interfaces, use
``"tcp:9999"`` or simply 9999. This port specification uses
``twisted.application.strports``, so you can make it listen on SSL
or even UNIX-domain sockets if you want.

Note that using any :class:`Manhole` requires that the `TwistedConch`_ package be
installed, and that you be using Twisted version 2.0 or later.

The buildmaster's SSH server will use a different host key than the
normal sshd running on a typical unix host. This will cause the ssh
client to complain about a `host key mismatch`, because it does not
realize there are two separate servers running on the same host. To
avoid this, use a clause like the following in your :file:`.ssh/config`
file:

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

After you have connected to a manhole instance, you will find yourself at a
Python prompt.  You have access to two objects: ``master`` (the BuildMaster)
and ``status`` (the master's Status object).  Most interesting objects on
the master can be reached from these two objects.

To aid in navigation, the ``show`` method is defined.  It displays the
non-method attributes of an object.

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
                  db_poll_interval : None
                            db_url : sqlite:///state.sqlite
                                  ...
    >>> show(master.botmaster.builders['win32'])
    data attributes of <Builder ''builder'' at 48963528>
                                  ...
    >>> win32 = _
    >>> win32.category = 'w32'

.. _Metrics-Options:

.. index:: c['metrics']

Metrics Options
~~~~~~~~~~~~~~~

::

    c['metrics'] = dict(log_interval=10, periodic_interval=10)

``c['metrics']`` can be a dictionary that configures various aspects
of the metrics subsystem. If ``c['metrics']`` is ``None``, then metrics
collection, logging and reporting will be disabled. 

``log_interval`` determines how often metrics should be logged to
twistd.log. It default to 60s. If set to 0 or ``None``, then logging of
metrics will be disabled. This value can be changed via a reconfig. 

``periodic_interval`` determines how often various non-event based
metrics are collected, such as memory usage, uncollectable garbage,
reactor delay. This defaults to 10s. If set to 0 or ``None``, then
periodic collection of this data is disabled. This value can also be
changed via a reconfig. 

Read more about metrics in the :ref:`Metrics` section of the documentation.

.. index:: c['user_managers']

.. _Users-Options:

Users Options
~~~~~~~~~~~~~

::

    from buildbot.process.users import manual
    c['user_managers'] = []
    c['user_managers'].append(manual.CommandlineUserManager(username="user",
                                                       passwd="userpw",
                                                       port=9990))

``c[user_manager]`` contains a list of ways to manually manage User Objects
within Buildbot (see :ref:`User-Objects`). Currently implemented is a
commandline tool `buildbot user`, described at length in :ref:`user`.
In the future, a web client will also be able to manage User Objects and
their attributes.

As shown above, to enable the `buildbot user` tool, you must initialize a
`CommandlineUserManager` instance in your `master.cfg`.
`CommandlineUserManager` instances require the following arguments:

``username``
    This is the `username` that will be registered on the PB connection
    and need to be used when calling `buildbot user`.

``passwd``
    This is the `passwd` that will be registered on the PB connection
    and need to be used when calling `buildbot user`.

``port``
    The PB connection `port` must be different than `c['slavePortnum']`
    and be specified when calling `buildbot user`

.. _Input-Validation:

.. index:: c['validation']

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
This validation is important since these values are often included in
command-line arguments executed on slaves.  Allowing arbitrary input from
untrusted users may raise security concerns.

The keys describe the type of input validated; the values are compiled regular
expressions against which the input will be matched.  The defaults for each
type of input are those given in the example, above.
    

.. _TwistedConch: http://twistedmatrix.com/trac/wiki/TwistedConch

