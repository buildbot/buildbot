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
If you plan to host a lot of data, you may consider using a more suitable database server.

If you want to use a database server (e.g., MySQL or Postgres) as the database backend for your Buildbot, use option `buildbot create-master --db` to specify the :ref:`connection string <Database-Specification>` for the database, and make sure that the same URL appears in the ``db_url`` of the :bb:cfg:`db` parameter in your configuration file.

Additional Requirements
~~~~~~~~~~~~~~~~~~~~~~~

Depending on the selected database, further Python packages will be required.
Consult the SQLAlchemy dialect list for a full description.
The most common choice for MySQL is

MySQL-Python: http://mysql-python.sourceforge.net/

  To communicate with MySQL, SQLAlchemy requires MySQL-Python.
  Any reasonably recent version of MySQL-Python should suffice.

The most common choice for Postgres is

Psycopg: http://initd.org/psycopg/

    SQLAlchemy uses Psycopg to communicate with Postgres.
    Any reasonably recent version should suffice.

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
You can use something like the following:

.. code-block:: none

    @weekly cd BASEDIR && find . -mindepth 2 i-path './public_html/*' \
        -prune -o -type f -mtime +14 -exec rm {} \;
    @weekly cd BASEDIR && find twistd.log* -mtime +14 -exec rm {} \;

Alternatively, you can configure a maximum number of old logs to be kept using the ``--log-count`` command line option when running ``buildslave create-slave`` or ``buildbot create-master``.

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
Again, :samp:`buildslave restart {BASEDIR}` will speed up the process.

.. _Contrib-Scripts:

Contrib Scripts
~~~~~~~~~~~~~~~

While some features of Buildbot are included in the distribution, others are only available in :file:`contrib/` in the source directory.
The latest versions of such scripts are available at http://github.com/buildbot/buildbot/tree/master/master/contrib.
