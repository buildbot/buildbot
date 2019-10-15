Buildmaster Setup
=================

.. _Creating-a-buildmaster:

Creating a buildmaster
----------------------

As you learned earlier (:ref:`System-Architecture`), the buildmaster runs on a central host (usually one that is publicly visible, so everybody can check on the status of the project), and controls all aspects of the buildbot system

You will probably wish to create a separate user account for the buildmaster, perhaps named ``buildmaster``.
Do not run the buildmaster as ``root``!

You need to choose a directory for the buildmaster, called the ``basedir``.
This directory will be owned by the buildmaster.
It will contain configuration, the database, and status information - including logfiles.
On a large buildmaster this directory will see a lot of activity, so it should be on a disk with adequate space and speed.

Once you've picked a directory, use the ``buildbot create-master`` command to create the directory and populate it with startup files:

.. code-block:: bash

    buildbot create-master -r basedir

You will need to create a :ref:`configuration file <Configuration>` before starting the buildmaster.
Most of the rest of this manual is dedicated to explaining how to do this.
A sample configuration file is placed in the working directory, named :file:`master.cfg.sample`, which can be copied to :file:`master.cfg` and edited to suit your purposes.

(Internal details: This command creates a file named :file:`buildbot.tac` that contains all the state necessary to create the buildmaster.
Twisted has a tool called ``twistd`` which can use this .tac file to create and launch a buildmaster instance.
Twistd takes care of logging and daemonization (running the program in the background).
:file:`/usr/bin/buildbot` is a front end which runs `twistd` for you.)

Your master will need a database to store the various information about your builds, and its configuration.
By default, the ``sqlite3`` backend will be used.
This needs no configuration, neither extra software.
All information will be stored in the file :file:`state.sqlite`.
Buildbot however supports multiple backends.
See :ref:`Database-Server` for more options.

Buildmaster Options
~~~~~~~~~~~~~~~~~~~

This section lists options to the ``create-master`` command.
You can also type ``buildbot create-master --help`` for an up-to-the-moment summary.

.. program:: buildbot create-master

.. option:: --force

    This option will allow to re-use an existing directory.

.. option:: --no-logrotate

    This disables internal worker log management mechanism.
    With this option worker does not override the default logfile name and its behaviour giving a possibility to control those with command-line options of twistd daemon.

.. option:: --relocatable

    This creates a "relocatable" ``buildbot.tac``, which uses relative paths instead of absolute paths, so that the buildmaster directory can be moved about.

.. option:: --config

    The name of the configuration file to use.
    This configuration file need not reside in the buildmaster directory.

.. option:: --log-size

    This is the size in bytes when to rotate the Twisted log files.
    The default is 10MiB.

.. option:: --log-count

    This is the number of log rotations to keep around.
    You can either specify a number or ``None`` to keep all :file:`twistd.log` files around.
    The default is 10.

.. option:: --db

    The database that the Buildmaster should use.
    Note that the same value must be added to the configuration file.

.. _Upgrading-an-Existing-Buildmaster:

Upgrading an Existing Buildmaster
---------------------------------

If you have just installed a new version of the Buildbot code, and you have buildmasters that were created using an older version, you'll need to upgrade these buildmasters before you can use them.
The upgrade process adds and modifies files in the buildmaster's base directory to make it compatible with the new code.

.. code-block:: bash

    buildbot upgrade-master basedir

This command will also scan your :file:`master.cfg` file for incompatibilities (by loading it and printing any errors or deprecation warnings that occur).
Each buildbot release tries to be compatible with configurations that worked cleanly (i.e. without deprecation warnings) on the previous release: any functions or classes that are to be removed will first be deprecated in a release, to give you a chance to start using the replacement.

The ``upgrade-master`` command is idempotent.
It is safe to run it multiple times.
After each upgrade of the Buildbot code, you should use ``upgrade-master`` on all your buildmasters.

.. warning::

   The ``upgrade-master`` command may perform database schema modifications.
   To avoid any data loss or corruption, it should **not** be interrupted.
   As a safeguard, it ignores all signals except ``SIGKILL``.

In general, Buildbot workers and masters can be upgraded independently, although some new features will not be available, depending on the master and worker versions.

Beyond this general information, read all of the sections below that apply to versions through which you are upgrading.

.. _Buildmaster-Version-specific-Notes:

Version-specific Notes
~~~~~~~~~~~~~~~~~~~~~~

Upgrading from Buildbot-0.8.x to Buildbot-0.9.x
'''''''''''''''''''''''''''''''''''''''''''''''

See :ref:`Upgrading to Nine` for a guide to upgrading from 0.8.x to 0.9.x

Upgrading a Buildmaster to Buildbot-0.7.6
'''''''''''''''''''''''''''''''''''''''''

The 0.7.6 release introduced the :file:`public_html/` directory, which contains :file:`index.html` and other files served by the ``WebStatus`` and ``Waterfall`` status displays.
The ``upgrade-master`` command will create these files if they do not already exist.
It will not modify existing copies, but it will write a new copy in e.g. :file:`index.html.new` if the new version differs from the version that already exists.

Upgrading a Buildmaster to Buildbot-0.8.0
'''''''''''''''''''''''''''''''''''''''''

Buildbot-0.8.0 introduces a database backend, which is SQLite by default.
The ``upgrade-master`` command will automatically create and populate this database with the changes the buildmaster has seen.
Note that, as of this release, build history is *not* contained in the database, and is thus not migrated.


Upgrading into a non-SQLite database
''''''''''''''''''''''''''''''''''''

If you are not using sqlite, you will need to add an entry into your :file:`master.cfg` to reflect the database version you are using.
The upgrade process does *not* edit your :file:`master.cfg` for you.
So something like:

.. code-block:: python

    # for using mysql:
    c['db_url'] = 'mysql://bbuser:<password>@localhost/buildbot'

Once the parameter has been added, invoke ``upgrade-master``.
This will extract the DB url from your configuration file.

.. code-block:: bash

    buildbot upgrade-master

See :ref:`Database-Specification` for more options to specify a database.
