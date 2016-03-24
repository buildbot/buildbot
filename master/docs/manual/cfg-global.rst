Global Configuration
--------------------

The keys in this section affect the operations of the buildmaster globally.

.. contents::
    :depth: 1
    :local:

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

   c['db_url'] = "mysql://user:pass@example.com/database_name?max_idle=300"

The ``max_idle`` argument for MySQL connections is unique to Buildbot, and should be set to something less than the ``wait_timeout`` configured for your server.
This controls the SQLAlchemy ``pool_recycle`` parameter, which defaults to no timeout.
Setting this parameter ensures that connections are closed and re-opened after the configured amount of idle time.
If you see errors such as ``_mysql_exceptions.OperationalError: (2006, 'MySQL server has gone away')``, this means your ``max_idle`` setting is probably too high.
``show global variables like 'wait_timeout';`` will show what the currently configured ``wait_timeout`` is on your MySQL server.

When using MySQL 5.x, if you see errors such as  ``BLOB, TEXT, GEOMETRY or JSON column state_string can not have a default value`` make sure to add  ``sql_mode='MYSQL40'`` in your configuration cnf file.

Buildbot requires ``use_unique=True`` and ``charset=utf8``, and will add them automatically, so they do not need to be specified in ``db_url``.

MySQL defaults to the MyISAM storage engine, but this can be overridden with the ``storage_engine`` URL argument.


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

Buildbot uses a message-queueing system to handle communication within the master.
Messages are used to indicate events within the master, and components that are interested in those events arrange to receive them.

The message queueing implementation is configured as a dictionary in the ``mq`` option.
The ``type`` key describes the type of MQ implemetation to be used.
Note that the implementation type cannot be changed in a reconfig.

The available implemenetation types are described in the following sections.

Simple
++++++

.. code-block:: python

    c['mq'] = {
        'type' : 'simple',
        'debug' : False,
    }

This is the default MQ implementation.
Similar to SQLite, it has no additional software dependencies, but does not support multi-master mode.

Note that this implementation also does not support message persistence across a restart of the master.
For example, if a change is received, but the master shuts down before the schedulers can create build requests for it, then those schedulers will not be notified of the change when the master starts again.

The ``debug`` key, which defaults to False, can be used to enable logging of every message produced on this master.

Wamp
++++

.. code-block:: python

    c['mq'] = {
        'type' : 'wamp',
        'router_url': 'ws://url/to/crossbar'
        'realm': 'buildbot'
        'debug' : False,
        'debug_websockets' : False,
        'debug_lowlevel' : False,
    }

This is a MQ implementation using `wamp <http://wamp.ws/>`_ protocol.
This implementation uses `Python Autobahn <http://autobahn.ws>`_ wamp client library, and is fully asynchronous (no use of threads)
To use this implementation, you need a wamp router like `Crossbar <http://crossbar.io>`_.
The implementation does not yet support wamp authentication yet.
This MQ allows buildbot to run in multi-master mode.

Note that this implementation also does not support message persistence across a restart of the master.
For example, if a change is received, but the master shuts down before the schedulers can create build requests for it, then those schedulers will not be notified of the change when the master starts again.

`router_url` key is mandatory, and should point to your router websocket url.
Buildbot is only supporting wamp over websocket, which is a sub-protocol of http.
SSL is supported using ``wss://`` instead of ``ws://``.
You must use a router with very reliable connection to the master.
If for some reason, the wamp connection is lost, then the master will stop, and should be restarted via a process manager.

`realm` key is optional and defaults to ``buildbot``, and configures the wamp realm to use for your buildbot messages.

The ``debug`` key, which defaults to False, can be used to enable logging of every message produced on this master.
``debug_websocket`` and ``debug_lowlevel``, enable more debug logs in autobahn.

.. bb:cfg:: multiMaster

.. _Multi-master-mode:

Multi-master mode
~~~~~~~~~~~~~~~~~

Normally buildbot operates using a single master process that uses the configured database to save state.

It is possible to configure buildbot to have multiple master processes that share state in the same database.
This has been well tested using a MySQL database.
There are several benefits of Multi-master mode:

* You can have large numbers of workers handling the same queue of build requests.
  A single master can only handle so many workers (the number is based on a number of factors including type of builds, number of builds, and master and worker IO and CPU capacity--there is no fixed formula).
  By adding another master which shares the queue of build requests, you can attach more workers to this additional master, and increase your build throughput.
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

When status notices are sent to users (e.g., by email or over IRC), :bb:cfg:`buildbotURL` will be used to create a URL to the specific build or problem that they are being notified about.

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
The default is 'gz', and the other valid option are 'raw' (no compression), 'gz' or 'lz4' (required lz4 package).

Please find below some stats extracted from 50x "Pyflakes" runs (results may differ according to log type).

.. csv-table:: Space saving details
   :header: "compression", "raw log size", "compressed log size", "space saving", "compression speed"

   "bz2", "2.981 MB", "0.603 MB", "79.77%", "3.433 MB/s"
   "gz", "2.981 MB", "0.568 MB", "80.95%", "6.604 MB/s"
   "lz4", "2.981 MB", "0.844 MB", "71.68%", "77.668 MB/s"

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

The :bb:cfg:`changeHorizon` key determines how many changes the master will keep a record of.
One place these changes are displayed is on the waterfall page.
This parameter defaults to 0, which means keep all changes indefinitely.

The :bb:cfg:`buildHorizon` specifies the minimum number of builds for each builder which should be kept on disk.
The :bb:cfg:`eventHorizon` specifies the minimum number of events to keep--events mostly describe connections and disconnections of workers, and are seldom helpful to developers.
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

    This parameter is the same as the deprecated global parameter :bb:cfg:`changeCacheSize`.
    Its default value is 10.

``Builds``
    The :bb:cfg:`buildCacheSize` parameter gives the number of builds for each builder which are cached in memory.
    This number should be larger than the number of builds required for commonly-used status displays (the waterfall or grid views), so that those displays do not miss the cache on a refresh.

    This parameter is the same as the deprecated global parameter :bb:cfg:`buildCacheSize`.
    Its default value is 15.

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

.. bb:cfg:: collapseRequests

.. index:: Builds; merging

Merging Build Requests
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   c['collapseRequests'] = True

This is a global default value for builders' :bb:cfg:`collapseRequests` parameter, and controls the merging of build requests.

This parameter can be overridden on a per-builder basis.
See :ref:`Collapsing-Build-Requests` for the allowed values for this parameter.

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

.. _Setting-the-PB-Port-for-Workers:

Setting the PB Port for Workers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    c['protocols'] = {"pb": {"port": 10000}}

The buildmaster will listen on a TCP port of your choosing for connections from workers.
It can also use this port for connections from remote Change Sources, status clients, and debug tools.
This port should be visible to the outside world, and you'll need to tell your worker admins about your choice.

It does not matter which port you pick, as long it is externally visible; however, you should probably use something larger than 1024, since most operating systems don't allow non-root processes to bind to low-numbered ports.
If your buildmaster is behind a firewall or a NAT box of some sort, you may have to configure your firewall to permit inbound connections to this port.

``c['protocols']['pb']['port']`` is a *strports* specification string, defined in the ``twisted.application.strports`` module (try ``pydoc twisted.application.strports`` to get documentation on the format).

This means that you can have the buildmaster listen on a localhost-only port by doing:

.. code-block:: python

   c['protocols'] = {"pb": {"port": "tcp:10000:interface=127.0.0.1"}}

This might be useful if you only run workers on the same machine, and they are all configured to contact the buildmaster at ``localhost:10000``.

.. note::

   In Buildbot versions <=0.8.8 you might see ``slavePortnum`` option.
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

.. note::

   Using any Manhole requires that ``pycrypto`` and ``pyasn1`` be installed.
   These are not part of the normal Buildbot dependencies.

`manhole.AuthorizedKeysManhole`
    You construct this with the name of a file that contains one SSH public key per line, just like :file:`~/.ssh/authorized_keys`.
    If you provide a non-absolute filename, it will be interpreted relative to the buildmaster's base directory.

`manhole.PasswordManhole`
    This one accepts SSH connections but asks for a username and password when authenticating.
    It accepts only one such pair.

`manhole.TelnetManhole`
    This accepts regular unencrypted telnet connections, and asks for a username/password pair before providing access.
    Because this username/password is transmitted in the clear, and because Manhole access to the buildmaster is equivalent to granting full shell privileges to both the buildmaster and all the workers (and to all accounts which then run code produced by the workers), it is  highly recommended that you use one of the SSH manholes instead.

::

    # some examples:
    from buildbot.plugins import util
    c['manhole'] = util.AuthorizedKeysManhole(1234, "authorized_keys")
    c['manhole'] = util.PasswordManhole(1234, "alice", "mysecretpassword")
    c['manhole'] = util.TelnetManhole(1234, "bob", "snoop_my_password_please")

The :class:`Manhole` instance can be configured to listen on a specific port.
You may wish to have this listening port bind to the loopback interface (sometimes known as `lo0`, `localhost`, or 127.0.0.1) to restrict access to clients which are running on the same host.

::

    from buildbot.plugins import util
    c['manhole'] = util.PasswordManhole("tcp:9999:interface=127.0.0.1","admin","passwd")

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

.. bb:cfg:: stats-service

Statistics Service
~~~~~~~~~~~~~~~~~~

The Statistics Service (stats service for short) supports for collecting arbitrary data from within a running Buildbot instance and export it do a number of storage backends.
Currently, only `InfluxDB <http://influxdb.com>`_ is supported as a storage backend.
Also, InfluxDB (or any other storage backend) is not a mandatory dependency.
Buildbot can run without it although :class:`StatsService` will be of no use in such a case.
At present, :class:`StatsService` can keep track of build properties, build times (start, end, duration) and arbitrary data produced inside Buildbot (more on this later).

Example usage:

.. code-block:: python

    captures = [stats.CaptureProperty('Builder1', 'tree-size-KiB'),
                stats.CaptureBuildDuration('Builder2')]
    c['services'] = []
    c['services'].append(stats.StatsService(
        storage_backends=[
            stats.InfluxStorageService('localhost', 8086, 'root', 'root', 'test', captures)
        ], name="StatsService"))

The ``services`` configuration value should be initialized as a list and a :class:`StatsService` instance should be appended to it as shown in the example above.

Statistics Service
++++++++++++++++++

.. py:class:: buildbot.statistics.stats_service.StatsService
   :noindex:

   This is the main class for statistics service.
   It is initialized in the master configuration as show in the example above.
   It takes two arguments:

   ``storage_backends``
     A list of storage backends (see :ref:`storage-backends`).
     In the example above, ``stats.InfluxStorageService`` is an instance of a storage backend.
     Each storage backend is an instances of subclasses of :py:class:`statsStorageBase`.
   ``name``
     The name of this service.

:py:meth:`yieldMetricsValue`: This method can be used to send arbitrary data for storage. (See :ref:`yieldMetricsValue` for more information.)

.. _capture-classes:

Capture Classes
+++++++++++++++

.. py:class:: buildbot.statistics.capture.CaptureProperty
   :noindex:

   Instance of this class declares which properties must be captured and sent to the :ref:`storage-backends`.
   It takes the following arguments:

   ``builder_name``
     The name of builder in which the property is recorded.
   ``property_name``
     The name of property needed to be recorded as a statistic.
   ``callback=None``
     (Optional) A custom callback function for this class.
     This callback function should take in two arguments - `build_properties` (dict) and `property_name` (str) and return a string that will be sent for storage in the storage backends.
   ``regex=False``
     If this is set to ``True``, then the property name can be a regular expression.
     All properties matching this regular expression will be sent for storage.

.. py:class:: buildbot.statistics.capture.CapturePropertyAllBuilders
   :noindex:

   Instance of this class declares which properties must be captured on all builders and sent to the :ref:`storage-backends`.
   It takes the following arguments:

   ``property_name``
     The name of property needed to be recorded as a statistic.
   ``callback=None``
     (Optional) A custom callback function for this class.
     This callback function should take in two arguments - `build_properties` (dict) and `property_name` (str) and return a string that will be sent for storage in the storage backends.
   ``regex=False``
     If this is set to ``True``, then the property name can be a regular expression.
     All properties matching this regular expression will be sent for storage.

.. py:class:: buildbot.statistics.capture.CaptureBuildStartTime
   :noindex:

   Instance of this class declares which builders' start times are to be captured and sent to :ref:`storage-backends`.
   It takes the following arguments:

   ``builder_name``
     The name of builder whose times are to be recorded.
   ``callback=None``
     (Optional) A custom callback function for this class.
     This callback function should take in a Python datetime object and return a string that will be sent for storage in the storage backends.

.. py:class:: buildbot.statistics.capture.CaptureBuildStartTimeAllBuilders
   :noindex:

   Instance of this class declares start times of all builders to be captured and sent to :ref:`storage-backends`.
   It takes the following arguments:

   ``callback=None``
     (Optional) A custom callback function for this class.
     This callback function should take in a Python datetime object and return a string that will be sent for storage in the storage backends.

.. py:class:: buildbot.statistics.capture.CaptureBuildEndTime
   :noindex:

   Exactly like :py:class:`CaptureBuildStartTime` except it declares the builders whose end time is to be recorded.
   The arguments are same as :py:class:`CaptureBuildStartTime`.

.. py:class:: buildbot.statistics.capture.CaptureBuildEndTimeAllBuilders
   :noindex:

   Exactly like :py:class:`CaptureBuildStartTimeAllBuilders` except it declares all builders' end time to be recorded.
   The arguments are same as :py:class:`CaptureBuildStartTimeAllBuilders`.

.. py:class:: buildbot.statistics.capture.CaptureBuildDuration
   :noindex:

   Instance of this class declares the builders whose build durations are to be recorded.
   It takes the following arguments:

   ``builder_name``
     The name of builder whose times are to be recorded.
   ``report_in='seconds'``
     Can be one of three: ``'seconds'``, ``'minutes'``, or ``'hours'``.
     This is the units in which the build time will be reported.
   ``callback=None``
     (Optional) A custom callback function for this class.
     This callback function should take in two Python datetime objects - a ``start_time`` and an ``end_time`` and return a string that will be sent for storage in the storage backends.

.. py:class:: buildbot.statistics.capture.CaptureBuildDurationAllBuilders
   :noindex:

   Instance of this class declares build durations to be recorded for all builders.
   It takes the following arguments:

   ``report_in='seconds'``
     Can be one of three: ``'seconds'``, ``'minutes'``, or ``'hours'``.
     This is the units in which the build time will be reported.
   ``callback=None``
     (Optional) A custom callback function for this class.
     This callback function should take in two Python datetime objects - a ``start_time`` and an ``end_time`` and return a string that will be sent for storage in the storage backends.

.. py:class:: buildbot.statistics.capture.CaptureData
   :noindex:

   Instance of this capture class is for capturing arbitrary data that is not stored as build-data.
   Needs to be used in conjunction with ``yieldMetricsValue`` (See :ref:`yieldMetricsValue`).
   Takes the following arguments:

   ``data_name``
     The name of data to be captured.
     Same as in ``yieldMetricsValue``.
   ``builder_name``
     The name of builder whose times are to be recorded.
   ``callback=None``
     The callback function for this class.
     This callback receives the data sent to  ``yieldMetricsValue`` as ``post_data`` (See :ref:`yieldMetricsValue`).
     It must return a string that is to be sent to the storage backends for storage.

.. py:class:: buildbot.statistics.capture.CaptureDataAllBuilders
   :noindex:

   Instance of this capture class for capturing arbitrary data that is not stored as build-data on all builders.
   Needs to be used in conjunction with ``yieldMetricsValue`` (See :ref:`yieldMetricsValue`).
   Takes the following arguments:

   ``data_name``
     The name of data to be captured.
     Same as in ``yieldMetricsValue``.
   ``callback=None``
     The callback function for this class.
     This callback receives the data sent to  ``yieldMetricsValue`` as ``post_data`` (See :ref:`yieldMetricsValue`).
     It must return a string that is to be sent to the storage backends for storage.

.. _yieldMetricsValue:

Using ``StatsService.yieldMetricsValue``
++++++++++++++++++++++++++++++++++++++++

Advanced users can modify ``BuildSteps`` to use ``StatsService.yieldMetricsValue`` which will send arbitrary data for storage to the ``StatsService``.
It takes the following arguments:

   ``data_name``
     The name of the data being sent or storage.
   ``post_data``
     A dictionary of key value pair that is sent for storage.
     The keys will act as columns in a database and the value is stored under that column.
   ``buildid``
     The integer build id of the current build.
     Obtainable in all ``BuildSteps``.

Along with using ``yieldMetricsValue``, the user will also need to use the ``CaptureData`` capture class.
As an example, we can add the following to a build step:

.. code-block:: python

    yieldMetricsValue('test_data_name', {'some_data': 'some_value'}, buildid)

Then, we can add in the master configuration a capture class like this:

.. code-block:: python

    captures = [CaptureBuildData('test_data_name', 'Builder1')]

Pass this ``captures`` list to a storage backend (as shown in the example at the top of this section) for capturing this data.

.. _storage-backends:

Storage Backends
++++++++++++++++

Storage backends are responsible for storing any statistics data sent to them.
A storage backend will generally be some sort of a database-server running on a machine.
(*Note*: This machine may be different from the one running :class:`BuildMaster`)

Currently, only `InfluxDB <http://influxdb.com>`_ is supported as a storage backend.

.. py:class:: buildbot.statistics.storage_backends.influxdb_client.InfluxStorageService
   :noindex:

   This class is a Buildbot client to the InfluxDB storage backend. `InfluxDB <http://influxdb.com>`_ is a distributed, time series database that employs a key-value pair storage system.

   It requires the following arguments:

   ``url``
     The URL where the service is running.
   ``port``
     The port on which the service is listening.
   ``user``
     Username of a InfluxDB user.
   ``password``
     Password for ``user``.
   ``db``
     The name of database to be used.
   ``captures``
     A list of objects of :ref:`capture-classes`.
     This tells which statistics are to be stored in this storage backend.
   ``name=None``
     (Optional) The name of this storage backend.

.. bb:cfg:: user_managers

.. _Users-Options:

Users Options
~~~~~~~~~~~~~

::

    from buildbot.plugins import util
    c['user_managers'] = []
    c['user_managers'].append(util.CommandlineUserManager(username="user",
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
This validation is important since these values are often included in command-line arguments executed on workers.
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

Note that :class:`SourceStamp`\s that are not created from version-control changes (e.g., those created by a :bb:sched:`Nightly` or :bb:sched:`Periodic` scheduler) may have an empty repository string, if the repository is not known to the scheduler.

Revision Link Helpers
+++++++++++++++++++++

Buildbot provides two helpers for generating revision links.
:class:`buildbot.revlinks.RevlinkMatcher` takes a list of regular expressions, and replacement text.
The regular expressions should all have the same number of capture groups.
The replacement text should have sed-style references to that capture groups (i.e. '\1' for the first capture group), and a single '%s' reference, for the revision ID.
The repository given is tried against each regular expression in turn.
The results are the substituted into the replacement text, along with the revision ID to obtain the revision link.

::

        from buildbot.plugins import util
        c['revlink'] = util.RevlinkMatch([r'git://notmuchmail.org/git/(.*)'],
                                          r'http://git.notmuchmail.org/git/\1/commit/%s')

:class:`buildbot.revlinks.RevlinkMultiplexer` takes a list of revision link callables, and tries each in turn, returning the first successful match.

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
