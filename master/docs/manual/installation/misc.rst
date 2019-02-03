Next Steps
==========

.. _Launching-the-daemons:

Launching the daemons
---------------------

Both the buildmaster and the worker run as daemon programs.
To launch them, pass the working directory to the :command:`buildbot` and :command:`buildbot-worker` commands, as appropriate:

.. code-block:: bash

    # start a master
    buildbot start [ BASEDIR ]
    # start a worker
    buildbot-worker start [ WORKER_BASEDIR ]

The *BASEDIR* is option and can be omitted if the current directory contains the buildbot configuration (the :file:`buildbot.tac` file).

.. code-block:: bash

    buildbot start

This command will start the daemon and then return, so normally it will not produce any output.
To verify that the programs are indeed running, look for a pair of files named :file:`twistd.log` and :file:`twistd.pid` that should be created in the working directory.
:file:`twistd.pid` contains the process ID of the newly-spawned daemon.

When the worker connects to the buildmaster, new directories will start appearing in its base directory.
The buildmaster tells the worker to create a directory for each Builder which will be using that worker.
All build operations are performed within these directories: CVS checkouts, compiles, and tests.

Once you get everything running, you will want to arrange for the buildbot daemons to be started at boot time.
One way is to use :command:`cron`, by putting them in a ``@reboot`` crontab entry [#f1]_

.. code-block:: none

    @reboot buildbot start [ BASEDIR ]

When you run :command:`crontab` to set this up, remember to do it as the buildmaster or worker account!
If you add this to your crontab when running as your regular account (or worse yet, root), then the daemon will run as the wrong user, quite possibly as one with more authority than you intended to provide.

It is important to remember that the environment provided to cron jobs and init scripts can be quite different than your normal runtime.
There may be fewer environment variables specified, and the :envvar:`PATH` may be shorter than usual.
It is a good idea to test out this method of launching the worker by using a cron job with a time in the near future, with the same command, and then check :file:`twistd.log` to make sure the worker actually started correctly.
Common problems here are for :file:`/usr/local` or :file:`~/bin` to not be on your :envvar:`PATH`, or for :envvar:`PYTHONPATH` to not be set correctly.
Sometimes :envvar:`HOME` is messed up too. If using systemd to launch :command:`buildbot-worker` it may be a good idea to specify a fixed :envvar:`PATH` using the :envvar:`Environment` directive,
see `systemd unit file example <https://github.com/buildbot/buildbot-contrib/blob/master/master/contrib/systemd/worker.service>`_

Some distributions may include conveniences to make starting buildbot at boot time easy.
For instance, with the default buildbot package in Debian-based distributions, you may only need to modify :file:`/etc/default/buildbot` (see also :file:`/etc/init.d/buildbot`, which reads the configuration in :file:`/etc/default/buildbot`).

Buildbot also comes with its own init scripts that provide support for controlling multi-worker and multi-master setups (mostly because they are based on the init script from the Debian package).
With a little modification these scripts can be used both on Debian and RHEL-based distributions and may thus prove helpful to package maintainers who are working on buildbot (or those that haven't yet split buildbot into master and worker packages).

.. code-block:: bash

    # install as /etc/default/buildbot-worker
    #         or /etc/sysconfig/buildbot-worker
    worker/contrib/init-scripts/buildbot-worker.default

    # install as /etc/default/buildmaster
    #         or /etc/sysconfig/buildmaster
    master/contrib/init-scripts/buildmaster.default

    # install as /etc/init.d/buildbot-worker
    worker/contrib/init-scripts/buildbot-worker.init.sh

    # install as /etc/init.d/buildmaster
    master/contrib/init-scripts/buildmaster.init.sh

    # ... and tell sysvinit about them
    chkconfig buildmaster reset
    # ... or
    update-rc.d buildmaster defaults

.. _Launching-worker-as-Windows-service:

Launching worker as Windows service
-----------------------------------

You can find information about installation of Buildbot as Windows service here
`RunningBuildbotOnWindows <http://trac.buildbot.net/wiki/RunningBuildbotOnWindows>`_.
Recent version of Buildbot worker has simplified configuration for Windows service.

.. code-block:: bat

    buildbot_worker_windows_service.exe --user YOURDOMAIN\theusername --password thepassword --startup auto install

automatically adds user rights to run Buildbot as service.

.. _Logfiles:

Logfiles
--------

While a buildbot daemon runs, it emits text to a logfile, named :file:`twistd.log`.
A command like ``tail -f twistd.log`` is useful to watch the command output as it runs.

The buildmaster will announce any errors with its configuration file in the logfile, so it is a good idea to look at the log at startup time to check for any problems.
Most buildmaster activities will cause lines to be added to the log.

.. _Shutdown:

Shutdown
--------

To stop a buildmaster or worker manually, use:

.. code-block:: bash

    buildbot stop [ BASEDIR ]
    # or
    buildbot-worker stop [ WORKER_BASEDIR ]

This simply looks for the :file:`twistd.pid` file and kills whatever process is identified within.

At system shutdown, all processes are sent a ``SIGKILL``.
The buildmaster and worker will respond to this by shutting down normally.

The buildmaster will respond to a ``SIGHUP`` by re-reading its config file.
Of course, this only works on Unix-like systems with signal support, and won't work on Windows.
The following shortcut is available:

.. code-block:: bash

    buildbot reconfig [ BASEDIR ]

When you update the Buildbot code to a new release, you will need to restart the buildmaster and/or worker before it can take advantage of the new code.
You can do a :samp:`buildbot stop {BASEDIR}` and :samp:`buildbot start {BASEDIR}` in quick succession, or you can use the ``restart`` shortcut, which does both steps for you:

.. code-block:: bash

    buildbot restart [ BASEDIR ]

Workers can similarly be restarted with:

.. code-block:: bash

    buildbot-worker restart [ BASEDIR ]

There are certain configuration changes that are not handled cleanly by ``buildbot reconfig``.
If this occurs, ``buildbot restart`` is a more robust tool to fully switch over to the new configuration.

``buildbot restart`` may also be used to start a stopped Buildbot instance.
This behaviour is useful when writing scripts that stop, start and restart Buildbot.

A worker may also be gracefully shutdown from the web UI.
This is useful to shutdown a worker without interrupting any current builds.
The buildmaster will wait until the worker has finished all its current builds, and will then tell the worker to shutdown.


.. [#f1]

   This ``@reboot`` syntax is understood by Vixie cron, which is the flavor usually provided with Linux systems.
   Other unices may have a cron that doesn't understand ``@reboot``
