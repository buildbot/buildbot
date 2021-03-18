Deployment
==========

This page aims at describing the common pitfalls and best practices when deploying buildbot.

.. contents::
    :depth: 1
    :local:

.. _Database-Server:

Using A Database Server
-----------------------

Buildbot uses the sqlite3 database backend by default.

.. important::

   SQLite3 is perfectly suitable for small setups with a few users.
   However, it does not scale well with large numbers of builders, workers and users.
   If you expect your Buildbot to grow over time, it is strongly advised to use a real database server (e.g., MySQL or Postgres).

If you want to use a database server as the database backend for your Buildbot, use option `buildbot create-master --db` to specify the :ref:`connection string <Database-Specification>` for the database, and make sure that the same URL appears in the ``db_url`` of the :bb:cfg:`db` parameter in your configuration file.

Server Setup Example
~~~~~~~~~~~~~~~~~~~~

Installing and configuring a database server can be complex.
Here is a minimalist example on how to install and configure a PostgreSQL server for your Buildbot on a recent Ubuntu system.

.. note::

   To install PostgreSQL on Ubuntu, you need root access.
   There are other ways to do it without root access (e.g. docker, build from source, etc.) but outside the scope of this example.

First, let's install the server with ``apt-get``:

.. code-block:: console

   $ sudo apt-get update
     <...>
   $ sudo apt-get install postgresql
     <...>
   $ sudo systemctl status postgresql@10-main.service
   ● postgresql@10-main.service - PostgreSQL Cluster 10-main
      Loaded: loaded (/lib/systemd/system/postgresql@.service; indirect; vendor preset: enabled)
      Active: active (running) since Wed 2019-05-29 11:33:40 CEST; 3min 1s ago
    Main PID: 24749 (postgres)
       Tasks: 7 (limit: 4915)
      CGroup: /system.slice/system-postgresql.slice/postgresql@10-main.service
              ├─24749 /usr/lib/postgresql/10/bin/postgres -D /var/lib/postgresql/10/main
              |       -c config_file=/etc/postgresql/10/main/postgresql.conf
              ├─24751 postgres: 10/main: checkpointer process
              ├─24752 postgres: 10/main: writer process
              ├─24753 postgres: 10/main: wal writer process
              ├─24754 postgres: 10/main: autovacuum launcher process
              ├─24755 postgres: 10/main: stats collector process
              └─24756 postgres: 10/main: bgworker: logical replication launcher

   May 29 11:33:38 ubuntu1804 systemd[1]: Starting PostgreSQL Cluster 10-main...
   May 29 11:33:40 ubuntu1804 systemd[1]: Started PostgreSQL Cluster 10-main.

Once the server is installed, create a user and associated database for your Buildbot.

.. code-block:: console

   $ sudo su - postgres
   postgres$ createuser -P buildbot
   Enter password for new role: bu1ldb0t
   Enter it again: bu1ldb0t
   postgres$ createdb -O buildbot buildbot
   postgres$ exit

After which, you can configure a proper `SQLAlchemy`_ URL:

.. code-block:: python

   c['db'] = {'db_url': 'postgresql://buildbot:bu1ldb0t@127.0.0.1/buildbot'}

And initialize the database tables with the following command:

.. code-block:: console

   $ buildbot upgrade-master
   checking basedir
   checking for running master
   checking master.cfg
   upgrading basedir
   creating master.cfg.sample
   upgrading database (postgresql://buildbot:xxxx@127.0.0.1/buildbot)
   upgrade complete

Additional Requirements
~~~~~~~~~~~~~~~~~~~~~~~

Depending on the selected database, further Python packages will be required.
Consult the `SQLAlchemy`_ dialect list for a full description.
The most common choice for MySQL is `mysqlclient`_.
Any reasonably recent version should suffice.

The most common choice for Postgres is `Psycopg`_.
Any reasonably recent version should suffice.

.. _SQLAlchemy: http://www.sqlalchemy.org/
.. _Psycopg: http://initd.org/psycopg/
.. _mysqlclient: https://github.com/PyMySQL/mysqlclient-python


.. _Maintenance:

Maintenance
-----------

The buildmaster can be configured to send out email notifications when a worker has been offline for a while.
Be sure to configure the buildmaster with a contact email address for each worker so these notifications are sent to someone who can bring it back online.

If you find you can no longer provide a worker to the project, please let the project admins know, so they can put out a call for a replacement.

The Buildbot records status and logs output continually, each time a build is performed.
The status tends to be small, but the build logs can become quite large.
Each build and log are recorded in a separate file, arranged hierarchically under the buildmaster's base directory.
To prevent these files from growing without bound, you should periodically delete old build logs.
A simple cron job to delete anything older than, say, two weeks should do the job.
The only trick is to leave the :file:`buildbot.tac` and other support files alone, for which :command:`find`'s ``-mindepth`` argument helps skip everything in the top directory.
You can use something like the following (assuming builds are stored in :file:`./builds/` directory):

.. code-block:: none

    @weekly cd BASEDIR && find . -mindepth 2 i-path './builds/*' \
        -prune -o -type f -mtime +14 -exec rm {} \;
    @weekly cd BASEDIR && find twistd.log* -mtime +14 -exec rm {} \;

Alternatively, you can configure a maximum number of old logs to be kept using the ``--log-count`` command line option when running ``buildbot-worker create-worker`` or ``buildbot create-master``.

.. _Troubleshooting:

Troubleshooting
---------------

Here are a few hints on diagnosing common problems.

.. _Starting-the-worker:

Starting the worker
~~~~~~~~~~~~~~~~~~~

Cron jobs are typically run with a minimal shell (:file:`/bin/sh`, not :file:`/bin/bash`), and tilde expansion is not always performed in such commands.
You may want to use explicit paths, because the :envvar:`PATH` is usually quite short and doesn't include anything set by your shell's startup scripts (:file:`.profile`, :file:`.bashrc`, etc).
If you've installed buildbot (or other Python libraries) to an unusual location, you may need to add a :envvar:`PYTHONPATH` specification (note that Python will do tilde-expansion on :envvar:`PYTHONPATH` elements by itself).
Sometimes it is safer to fully-specify everything:

.. code-block:: none

    @reboot PYTHONPATH=~/lib/python /usr/local/bin/buildbot \
        start /usr/home/buildbot/basedir

Take the time to get the ``@reboot`` job set up.
Otherwise, things will work fine for a while, but the first power outage or system reboot you have will stop the worker with nothing but the cries of sorrowful developers to remind you that it has gone away.

.. _Connecting-to-the-buildmaster:

Connecting to the buildmaster
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the worker cannot connect to the buildmaster, the reason should be described in the :file:`twistd.log` logfile.
Some common problems are an incorrect master hostname or port number, or a mistyped bot name or password.
If the worker loses the connection to the master, it is supposed to attempt to reconnect with an exponentially-increasing backoff.
Each attempt (and the time of the next attempt) will be logged.
If you get impatient, just manually stop and re-start the worker.

When the buildmaster is restarted, all workers will be disconnected, and will attempt to reconnect as usual.
The reconnect time will depend upon how long the buildmaster is offline (i.e. how far up the exponential backoff curve the workers have travelled).
Again, :samp:`buildbot-worker restart {BASEDIR}` will speed up the process.

.. _Logging-to-stdout:

Logging to stdout
~~~~~~~~~~~~~~~~~

It can be useful to let buildbot output it's log to stdout instead of a logfile.
For example when running via docker, supervisor or when buildbot is started with --no-daemon.
This can be accomplished by editing :file:`buildbot.tac`. It's already enabled in the docker :file:`buildbot.tac`
Change the line: `application.setComponent(ILogObserver, FileLogObserver(logfile).emit)`
to: `application.setComponent(ILogObserver, FileLogObserver(sys.stdout).emit)`

.. _Debugging-with-the-python-debugger:

Debugging with the python debugger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes it's necessary to see what is happening inside a program.
To enable this, start buildbot with:

.. code-block:: none

      twistd --no_save -n -b --logfile=- -y buildbot.tac

This will load the debugger on every exception and breakpoints in the program.
More information on the python debugger can be found here: https://docs.python.org/3/library/pdb.html

.. _Contrib-Scripts:

Contrib Scripts
~~~~~~~~~~~~~~~

While some features of Buildbot are included in the distribution, others are only available in :contrib-src:`master/contrib/` in the ``buildbot-contrib`` source directory.
The latest versions of such scripts are available at :contrib-src:`master/contrib`.
