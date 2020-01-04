Worker Setup
============

.. _Creating-a-worker:

Creating a worker
-----------------

Typically, you will be adding a worker to an existing buildmaster, to provide additional architecture coverage.
The Buildbot administrator will give you several pieces of information necessary to connect to the buildmaster.
You should also be somewhat familiar with the project being tested, so you can troubleshoot build problems locally.

The Buildbot exists to make sure that the project's stated ``how to build it`` process actually works.
To this end, the worker should run in an environment just like that of your regular developers.
Typically the project build process is documented somewhere (:file:`README`, :file:`INSTALL`, etc), in a document that should mention all library dependencies and contain a basic set of build instructions.
This document will be useful as you configure the host and account in which the worker runs.

Here's a good checklist for setting up a worker:

1. Set up the account

  It is recommended (although not mandatory) to set up a separate user account for the worker.
  This account is frequently named ``buildbot`` or ``worker``.
  This serves to isolate your personal working environment from that of the worker's, and helps to minimize the security threat posed by letting possibly-unknown contributors run arbitrary code on your system.
  The account should have a minimum of fancy init scripts.

2. Install the Buildbot code

  Follow the instructions given earlier (:ref:`Installing-the-code`).
  If you use a separate worker account, and you didn't install the Buildbot code to a shared location, then you will need to install it with ``--home=~`` for each account that needs it.

3. Set up the host

  Make sure the host can actually reach the buildmaster.
  Usually the buildmaster is running a status webserver on the same machine, so simply point your web browser at it and see if you can get there.
  Install whatever additional packages or libraries the project's INSTALL document advises.
  (or not: if your worker is supposed to make sure that building without optional libraries still works, then don't install those libraries.)

  Again, these libraries don't necessarily have to be installed to a site-wide shared location, but they must be available to your build process.
  Accomplishing this is usually very specific to the build process, so installing them to :file:`/usr` or :file:`/usr/local` is usually the best approach.

4. Test the build process

  Follow the instructions in the :file:`INSTALL` document, in the worker's account.
  Perform a full CVS (or whatever) checkout, configure, make, run tests, etc.
  Confirm that the build works without manual fussing.
  If it doesn't work when you do it by hand, it will be unlikely to work when the Buildbot attempts to do it in an automated fashion.

5. Choose a base directory

  This should be somewhere in the worker's account, typically named after the project which is being tested.
  The worker will not touch any file outside of this directory.
  Something like :file:`~/Buildbot` or :file:`~/Workers/fooproject` is appropriate.

6. Get the buildmaster host/port, botname, and password

  When the Buildbot admin configures the buildmaster to accept and use your worker, they will provide you with the following pieces of information:

  * your worker's name
  * the password assigned to your worker
  * the hostname and port number of the buildmaster, i.e. `<http://buildbot.example.org:8007>`__

7. Create the worker

  Now run the 'worker' command as follows:

      :samp:`buildbot-worker create-worker {BASEDIR} {MASTERHOST}:{PORT} {WORKERNAME} {PASSWORD}`

  This will create the base directory and a collection of files inside, including the :file:`buildbot.tac` file that contains all the information you passed to the :command:`buildbot` command.

8. Fill in the hostinfo files

  When it first connects, the worker will send a few files up to the buildmaster which describe the host that it is running on.
  These files are presented on the web status display so that developers have more information to reproduce any test failures that are witnessed by the Buildbot.
  There are sample files in the :file:`info` subdirectory of the Buildbot's base directory.
  You should edit these to correctly describe you and your host.

  :file:`{BASEDIR}/info/admin` should contain your name and email address.
  This is the ``worker admin address``, and will be visible from the build status page (so you may wish to munge it a bit if address-harvesting spambots are a concern).

  :file:`{BASEDIR}/info/host` should be filled with a brief description of the host: OS, version, memory size, CPU speed, versions of relevant libraries installed, and finally the version of the Buildbot code which is running the worker.

  The optional :file:`{BASEDIR}/info/access_uri` can specify a URI which will connect a user to the machine.
  Many systems accept ``ssh://hostname`` URIs for this purpose.

  If you run many workers, you may want to create a single :file:`~worker/info` file and share it among all the workers with symlinks.

.. _Worker-Options:

Worker Options
~~~~~~~~~~~~~~

There are a handful of options you might want to use when creating the worker with the :samp:`buildbot-worker create-worker <options> DIR <params>` command.
You can type ``buildbot-worker create-worker --help`` for a summary.
To use these, just include them on the ``buildbot-worker create-worker`` command line, like this

.. code-block:: bash

    buildbot-worker create-worker --umask=0o22 ~/worker buildmaster.example.org:42012 {myworkername} {mypasswd}

.. program:: buildbot-worker create-worker

.. option:: --no-logrotate

    This disables internal worker log management mechanism.
    With this option worker does not override the default logfile name and its behaviour giving a possibility to control those with command-line options of twistd daemon.

.. option:: --umask

    This is a string (generally an octal representation of an integer) which will cause the worker process' ``umask`` value to be set shortly after initialization.
    The ``twistd`` daemonization utility forces the umask to 077 at startup (which means that all files created by the worker or its child processes will be unreadable by any user other than the worker account).
    If you want build products to be readable by other accounts, you can add ``--umask=0o22`` to tell the worker to fix the umask after twistd clobbers it.
    If you want build products to be *writable* by other accounts too, use ``--umask=0o000``, but this is likely to be a security problem.

.. option:: --keepalive

    This is a number that indicates how frequently ``keepalive`` messages should be sent from the worker to the buildmaster, expressed in seconds.
    The default (600) causes a message to be sent to the buildmaster at least once every 10 minutes.
    To set this to a lower value, use e.g. ``--keepalive=120``.

    If the worker is behind a NAT box or stateful firewall, these messages may help to keep the connection alive: some NAT boxes tend to forget about a connection if it has not been used in a while.
    When this happens, the buildmaster will think that the worker has disappeared, and builds will time out.
    Meanwhile the worker will not realize than anything is wrong.

.. option:: --maxdelay

    This is a number that indicates the maximum amount of time the worker will wait between connection attempts, expressed in seconds.
    The default (300) causes the worker to wait at most 5 minutes before trying to connect to the buildmaster again.

.. option:: --maxretries

    This is a number that indicates the maximum number of time the worker will make connection attempts.
    After that amount, the worker process will stop.
    This option is useful for :ref:`Latent-Workers` to avoid consuming resources in case of misconfiguration or master failure.

    For VM based latent workers, the user is responsible for halting the system when Buildbot worker has exited.
    This feature is heavily OS dependent, and cannot be managed by Buildbot worker.
    For example with systemd_, one can add ``ExecStopPost=shutdown now`` to the Buildbot worker service unit configuration.

    .. _systemd: https://www.freedesktop.org/software/systemd/man/systemd.service.html

.. option:: --log-size

    This is the size in bytes when to rotate the Twisted log files.

.. option:: --log-count

    This is the number of log rotations to keep around.
    You can either specify a number or ``None`` to keep all :file:`twistd.log` files around.
    The default is 10.

.. option:: --allow-shutdown

    Can also be passed directly to the Worker constructor in :file:`buildbot.tac`.
    If set, it allows the worker to initiate a graceful shutdown, meaning that it will ask the master to shut down the worker when the current build, if any, is complete.

    Setting allow_shutdown to ``file`` will cause the worker to watch :file:`shutdown.stamp` in basedir for updates to its mtime.
    When the mtime changes, the worker will request a graceful shutdown from the master.
    The file does not need to exist prior to starting the worker.

    Setting allow_shutdown to ``signal`` will set up a SIGHUP handler to start a graceful shutdown.
    When the signal is received, the worker will request a graceful shutdown from the master.

    The default value is ``None``, in which case this feature will be disabled.

    Both master and worker must be at least version 0.8.3 for this feature to work.

.. option:: --use-tls

    Can also be passed directly to the Worker constructor in :file:`buildbot.tac`.
    If set, the generated connection string starts with ``tls`` instead of with ``tcp``, allowing encrypted connection to the buildmaster.
    Make sure the worker trusts the buildmasters certificate. If you have an non-authoritative certificate (CA is self-signed) see ``connection_string`` below.

.. _Other-Worker-Configuration:

Other Worker Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

``unicode_encoding``
    This represents the encoding that Buildbot should use when converting unicode commandline arguments into byte strings in order to pass to the operating system when spawning new processes.

    The default value is what Python's :func:`sys.getfilesystemencoding()` returns, which on Windows is 'mbcs', on Mac OSX is 'utf-8', and on Unix depends on your locale settings.

    If you need a different encoding, this can be changed in your worker's :file:`buildbot.tac` file by adding a ``unicode_encoding`` argument to the Worker constructor.

.. code-block:: python

    s = Worker(buildmaster_host, port, workername, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay,
               unicode_encoding='utf-8', allow_shutdown='signal')

.. _Worker-TLS-Config:

Worker TLS Configuration
~~~~~~~~~~~~~~~~~~~~~~~~

``tls``
    See ``--useTls`` option above as an alternative to setting the ``conneciton_string`` manually.


``connection_string``
    For TLS connections to the master the ``connection_string``-argument must be used to ``Worker.__init__`` function. ``buildmaster_host`` and ``port`` must then be ``None``.

    ``connection_string`` will be used to create a client endpoint with clientFromString_. An example of ``connection_string`` is ``"TLS:buildbot-master.com:9989"``.

    See more about how to formulate the connection string in ConnectionStrings_.

    Example TLS connection string:

    .. code-block:: python

        s = Worker(None, None, workername, passwd, basedir, keepalive,
                   connection_string='TLS:buildbot-master.com:9989')

    Make sure the worker trusts the masters certificate. If you have an non-authoritative certificate
    (CA is self-signed) the trustRoot parameter can be used.

    .. code-block:: python

        s = Worker(None, None, workername, passwd, basedir, keepalive,
                   connection_string=
                   'TLS:buildbot-master.com:9989:trustRoots=/dir-with-ca-certs')


    It must point to a directory with PEM-encoded certificates in files with file ending .pem. For example:

    .. code-block:: bash

        $ cat /dir-with-ca-certs/ca.pem
        -----BEGIN CERTIFICATE-----
        MIIE9DCCA9ygAwIBAgIJALEqLrC/m1w3MA0GCSqGSIb3DQEBCwUAMIGsMQswCQYD
        VQQGEwJaWjELMAkGA1UECBMCUUExEDAOBgNVBAcTB05vd2hlcmUxETAPBgNVBAoT
        CEJ1aWxkYm90MRkwFwYDVQQLExBEZXZlbG9wbWVudCBUZWFtMRQwEgYDVQQDEwtC
        dWlsZGJvdCBDQTEQMA4GA1UEKRMHRWFzeVJTQTEoMCYGCSqGSIb3DQEJARYZYnVp
        bGRib3RAaW50ZWdyYXRpb24udGVzdDAeFw0xNjA5MDIxMjA5NTJaFw0yNjA4MzEx
        MjA5NTJaMIGsMQswCQYDVQQGEwJaWjELMAkGA1UECBMCUUExEDAOBgNVBAcTB05v
        d2hlcmUxETAPBgNVBAoTCEJ1aWxkYm90MRkwFwYDVQQLExBEZXZlbG9wbWVudCBU
        ZWFtMRQwEgYDVQQDEwtCdWlsZGJvdCBDQTEQMA4GA1UEKRMHRWFzeVJTQTEoMCYG
        CSqGSIb3DQEJARYZYnVpbGRib3RAaW50ZWdyYXRpb24udGVzdDCCASIwDQYJKoZI
        hvcNAQEBBQADggEPADCCAQoCggEBALJZcC9j4XYBi1fYT/fibY2FRWn6Qh74b1Pg
        I7iIde6Sf3DPdh/ogYvZAT+cIlkZdo4v326d0EkuYKcywDvho8UeET6sIYhuHPDW
        lRl1Ret6ylxpbEfxFNvMoEGNhYAP0C6QS2eWEP9LkV2lCuMQtWWzdedjk+efqBjR
        Gozaim0lr/5lx7bnVx0oRLAgbI5/9Ukbopansfr+Cp9CpFpbNPGZSmELzC3FPKXK
        5tycj8WEqlywlha2/VRnCZfYefB3aAuQqQilLh+QHyhn6hzc26+n5B0l8QvrMkOX
        atKdznMLzJWGxS7UwmDKcsolcMAW+82BZ8nUCBPF3U5PkTLO540CAwEAAaOCARUw
        ggERMB0GA1UdDgQWBBT7A/I+MZ1sFFJ9jikYkn51Q3wJ+TCB4QYDVR0jBIHZMIHW
        gBT7A/I+MZ1sFFJ9jikYkn51Q3wJ+aGBsqSBrzCBrDELMAkGA1UEBhMCWloxCzAJ
        BgNVBAgTAlFBMRAwDgYDVQQHEwdOb3doZXJlMREwDwYDVQQKEwhCdWlsZGJvdDEZ
        MBcGA1UECxMQRGV2ZWxvcG1lbnQgVGVhbTEUMBIGA1UEAxMLQnVpbGRib3QgQ0Ex
        EDAOBgNVBCkTB0Vhc3lSU0ExKDAmBgkqhkiG9w0BCQEWGWJ1aWxkYm90QGludGVn
        cmF0aW9uLnRlc3SCCQCxKi6wv5tcNzAMBgNVHRMEBTADAQH/MA0GCSqGSIb3DQEB
        CwUAA4IBAQCJGJVMAmwZRK/mRqm9E0e3s4YGmYT2jwX5IX17XljEy+1cS4huuZW2
        33CFpslkT1MN/r8IIZWilxT/lTujHyt4eERGjE1oRVKU8rlTH8WUjFzPIVu7nkte
        09abqynAoec8aQukg79NRCY1l/E2/WzfnUt3yTgKPfZmzoiN0K+hH4gVlWtrizPA
        LaGwoslYYTA6jHNEeMm8OQLNf17OTmAa7EpeIgVpLRCieI9S3JIG4WYU8fVkeuiU
        cB439SdixU4cecVjNfFDpq6JM8N6+DQoYOSNRt9Dy0ioGyx5D4lWoIQ+BmXQENal
        gw+XLyejeNTNgLOxf9pbNYMJqxhkTkoE
        -----END CERTIFICATE-----


    Using TCP in ``connection_string`` is the equivalent as using the ``buildmaster_host`` and ``port`` arguments.

    .. code-block:: python

        s = Worker(None, None, workername, passwd, basedir, keepalive
                   connection_string='TCP:buildbot-master.com:9989')


    is equivalent to

    .. code-block:: python

        s = Worker('buildbot-master.com', 9989, workername, passwd, basedir,
                   keepalive)




.. _ConnectionStrings: https://twistedmatrix.com/documents/current/core/howto/endpoints.html
.. _clientFromString: https://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.clientFromString.html

.. _Upgrading-an-Existing-Worker:

Upgrading an Existing Worker
----------------------------

.. _Worker-Version-specific-Notes:

Version-specific Notes
~~~~~~~~~~~~~~~~~~~~~~

During project lifetime worker has transitioned over few states:

1. Before Buildbot version 0.8.1 worker were integral part of ``buildbot`` package distribution.
2. Starting from Buildbot version 0.8.1 worker were extracted from ``buildbot`` package to ``buildbot-slave`` package.
3. Starting from Buildbot version 0.9.0 the ``buildbot-slave`` package was renamed to ``buildbot-worker``.

Upgrading a Worker to buildbot-slave 0.8.1
''''''''''''''''''''''''''''''''''''''''''

Before Buildbot version 0.8.1, the Buildbot master and worker were part of the same distribution.
As of version 0.8.1, the worker is a separate distribution.

As of this release, you will need to install ``buildbot-slave`` to run a worker.

Any automatic startup scripts that had run ``buildbot start`` for previous versions should be changed to run ``buildslave start`` instead.

If you are running a version later than 0.8.1, then you can skip the remainder of this section: the ``upgrade-slave`` command will take care of this.
If you are upgrading directly to 0.8.1, read on.

The existing :file:`buildbot.tac` for any workers running older versions will need to be edited or replaced.
If the loss of cached worker state (e.g., for Source steps in copy mode) is not problematic, the easiest solution is to simply delete the worker directory and re-run ``buildslave create-slave``.

If deleting the worker directory is problematic, the change to :file:`buildbot.tac` is simple.
On line 3, replace:

.. code-block:: python

    from buildbot.slave.bot import BuildSlave

with:

.. code-block:: python

    from buildslave.bot import BuildSlave

After this change, the worker should start as usual.

Upgrading from `0.8.1` to the latest ``0.8.*`` version of buildbot-slave
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If you have just installed a new version of Buildbot-slave, you may need to take some steps to upgrade it.
If you are upgrading to version 0.8.2 or later, you can run

.. code-block:: bash

    buildslave upgrade-slave /path/to/worker/dir

Upgrading from the latest version of ``buildbot-slave`` to ``buildbot-worker``
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

If the loss of cached worker state (e.g., for Source steps in copy mode) is not problematic, the easiest solution is to simply delete the worker directory and re-run ``buildbot-worker create-worker``.

If deleting the worker directory is problematic, you can change :file:`buildbot.tac` in the following way:

1. Replace:

   .. code-block:: python

       from buildslave.bot import BuildSlave

   with:

   .. code-block:: python

       from buildbot_worker.bot import Worker

2. Replace:

   .. code-block:: python

       application = service.Application('buildslave')

   with:

   .. code-block:: python

       application = service.Application('buildbot-worker')

3. Replace:

   .. code-block:: python

       s = BuildSlave(buildmaster_host, port, slavename, passwd, basedir,
                      keepalive, usepty, umask=umask, maxdelay=maxdelay,
                      numcpus=numcpus, allow_shutdown=allow_shutdown)

   with:

   .. code-block:: python

       s = Worker(buildmaster_host, port, slavename, passwd, basedir,
                  keepalive, umask=umask, maxdelay=maxdelay,
                  numcpus=numcpus, allow_shutdown=allow_shutdown)

See :ref:`Transition to "Worker" Terminology <Worker-Transition-Buildbot-Worker>` for details of changes in version Buildbot ``0.9.0``.
