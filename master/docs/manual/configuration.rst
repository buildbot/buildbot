.. _Configuration:

Configuration
=============

The buildbot's behavior is defined by the *config file*, which
normally lives in the :file:`master.cfg` file in the buildmaster's base
directory (but this can be changed with an option to the
:command:`buildbot create-master` command). This file completely specifies
which :class:`Builder`\s are to be run, which slaves they should use, how
:class:`Change`\s should be tracked, and where the status information is to be
sent. The buildmaster's :file:`buildbot.tac` file names the base
directory; everything else comes from the config file.

A sample config file was installed for you when you created the
buildmaster, but you will need to edit it before your buildbot will do
anything useful.

This chapter gives an overview of the format of this file and the
various sections in it. You will need to read the later chapters to
understand how to fill in each section properly.

.. _Config-File-Format:

Config File Format
------------------

The config file is, fundamentally, just a piece of Python code which
defines a dictionary named ``BuildmasterConfig``, with a number of
keys that are treated specially. You don't need to know Python to do
basic configuration, though, you can just copy the syntax of the
sample file. If you *are* comfortable writing Python code,
however, you can use all the power of a full programming language to
achieve more complicated configurations.

The ``BuildmasterConfig`` name is the only one which matters: all
other names defined during the execution of the file are discarded.
When parsing the config file, the Buildmaster generally compares the
old configuration with the new one and performs the minimum set of
actions necessary to bring the buildbot up to date: :class:`Builder`\s which are
not changed are left untouched, and :class:`Builder`\s which are modified get to
keep their old event history.

The beginning of the :file:`master.cfg` file
typically starts with something like::

    BuildmasterConfig = c = {}

Therefore a config key of ``change_source`` will usually appear in
:file:`master.cfg` as ``c['change_source']``.

See :ref:`Configuration-Index` for a full list of ``BuildMasterConfig``
keys.

.. _Basic-Python-Syntax:

Basic Python Syntax
~~~~~~~~~~~~~~~~~~~

Python comments start with a hash character ``#``, tuples are defined with
``(parenthesis, pairs)``, and lists (arrays) are defined with ``[square,
brackets]``. Tuples and lists are mostly interchangeable. Dictionaries (data
structures which map *keys* to *values*) are defined with curly braces:
``{'key1': value1, 'key2': value2}``. Function calls (and object
instantiation) can use named parameters, like ``w =
html.Waterfall(http_port=8010)``.

The config file starts with a series of ``import`` statements, which make
various kinds of :class:`Step`\s and :class:`Status` targets available for later use. The main
``BuildmasterConfig`` dictionary is created, then it is populated with a
variety of keys, described section-by-section in subsequent chapters. 

.. _Predefined-Config-File-Symbols:

Predefined Config File Symbols
------------------------------

The following symbols are automatically available for use in the configuration
file.

``basedir``
    the base directory for the buildmaster. This string has not been
    expanded, so it may start with a tilde. It needs to be expanded before
    use. The config file is located in ::
    
        os.path.expanduser(os.path.join(basedir, 'master.cfg'))
``__file__``
   the absolute path of the config file. The config file's directory is located in
   ``os.path.dirname(__file__)``.

.. _Testing-the-Config-File:

Testing the Config File
-----------------------

To verify that the config file is well-formed and contains no deprecated or
invalid elements, use the ``checkconfig`` command, passing it either a master
directory or a config file.

.. code-block:: bash

   % buildbot checkconfig master.cfg
   Config file is good!
   # or
   % buildbot checkconfig /tmp/masterdir
   Config file is good!

If the config file has deprecated features (perhaps because you've
upgraded the buildmaster and need to update the config file to match),
they will be announced by checkconfig. In this case, the config file
will work, but you should really remove the deprecated items and use
the recommended replacements instead:

.. code-block:: bash


   % buildbot checkconfig master.cfg
   /usr/lib/python2.4/site-packages/buildbot/master.py:559: DeprecationWarning: c['sources'] is
   deprecated as of 0.7.6 and will be removed by 0.8.0 . Please use c['change_source'] instead.
     warnings.warn(m, DeprecationWarning)
   Config file is good!


If the config file is simply broken, that will be caught too:

.. code-block:: bash

   % buildbot checkconfig master.cfg
   Traceback (most recent call last):
     File "/usr/lib/python2.4/site-packages/buildbot/scripts/runner.py", line 834, in doCheckConfig
       ConfigLoader(configFile)
     File "/usr/lib/python2.4/site-packages/buildbot/scripts/checkconfig.py", line 31, in __init__
       self.loadConfig(configFile)
     File "/usr/lib/python2.4/site-packages/buildbot/master.py", line 480, in loadConfig
       exec f in localDict
     File "/home/warner/BuildBot/master/foolscap/master.cfg", line 90, in ?
       c[bogus] = "stuff"
   NameError: name 'bogus' is not defined

.. _Loading-the-Config-File:
    
Loading the Config File
-----------------------

The config file is only read at specific points in time. It is first
read when the buildmaster is launched. If the configuration is invalid, the
master will display the errors in the console output, but will not exit.

.. _Reloading-the-config-file-reconfig:

Reloading the Config File (reconfig)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are on the system hosting the buildmaster, you can send a ``SIGHUP``
signal to it: the :command:`buildbot` tool has a shortcut for this:

.. code-block:: none

    buildbot reconfig BASEDIR

This command will show you all of the lines from :file:`twistd.log`
that relate to the reconfiguration. If there are any problems during
the config-file reload, they will be displayed in these lines.

When reloading the config file, the buildmaster will endeavor to
change as little as possible about the running system. For example,
although old status targets may be shut down and new ones started up,
any status targets that were not changed since the last time the
config file was read will be left running and untouched. Likewise any
:class:`Builder`\s which have not been changed will be left running. If a
:class:`Builder` is modified (say, the build process is changed) while a :class:`Build`
is currently running, that :class:`Build` will keep running with the old
process until it completes. Any previously queued :class:`Build`\s (or :class:`Build`\s
which get queued after the reconfig) will use the new process.

.. warning:: Buildbot's reconfiguration system is fragile for a few difficult-to-fix
   reasons:

    * Any modules imported by the configuration file are not automatically reloaded.
      Python modules such as http://pypi.python.org/pypi/lazy-reload may help
      here, but reloading modules is fraught with subtlties and difficult-to-decipher
      failure cases.

    * During the reconfiguration, active internal objects are divorced from the service
      hierarchy, leading to tracebacks in the web interface and other components. These
      are ordinarily transient, but with HTTP connection caching (either by the browser or
      an intervening proxy) they can last for a long time.

    * If the new configuration file is invalid, it is possible for Buildbot's
      internal state to be corrupted, leading to undefined results.  When this
      occurs, it is best to restart the master.

    * For more advanced configurations, it is impossible for Buildbot to tell if the
      configuration for a :class:`Builder` or :class:`Scheduler` has chanaged, and thus the :class:`Builder` or
      :class:`Scheduler` will always be reloaded.  This occurs most commonly when a callable
      is passed as a configuration parameter.


   The bbproto project (at https://github.com/dabrahams/bbproto) may help to
   construct large (multi-file) configurations which can be effectively reloaded
   and reconfigured.

Reconfig by Debug Client
~~~~~~~~~~~~~~~~~~~~~~~~

The debug tool (:samp:`buildbot debugclient --master {HOST}:{PORT}`) has a
:guilabel:`Reload .cfg` button which will also trigger a reload. In the
future, there will be other ways to accomplish this step (probably a
password-protected button on the web page, as well as a privileged IRC
command).


.. _Global-Configuration:

Global Configuration
--------------------

The keys in this section affect the operations of the buildmaster globally.


.. include:: cfg-global.rsi
.. include:: cfg-changesources.rsi
.. include:: cfg-schedulers.rsi
.. include:: cfg-buildslaves.rsi
.. include:: cfg-builders.rsi
.. include:: cfg-buildfactories.rsi
.. include:: cfg-buildsteps.rsi
.. include:: cfg-interlocks.rsi
.. include:: cfg-statustargets.rsi
