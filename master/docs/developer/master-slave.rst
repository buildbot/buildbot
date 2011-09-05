Master-Slave API
================

This section is a (very incomplete) description of the master-slave interface.
The interface is based on Twisted's Perspective Broker.

Connection
~~~~~~~~~~

The slave connects to the master, using the parameters supplied to
:command:`buildslave create-slave`.  It uses a reconnecting process with an
exponential backoff, and will automatically reconnect on disconnection.

.. py:class:: buildslave.bot.Bot

Once connected, the slave authenticates with the Twisted Cred (newcred)
mechanism, using the username and password supplied to :command:`buildslave
create-slave`.  The *mind* is the slave bot instance (class
:class:`buildslave.bot.Bot`).

.. py:class:: buildbot.master.Dispatcher
.. py:class:: buildbot.buildslave.BuildSlave

On the master side, the realm is implemented by
:class:`buildbot.master.Dispatcher`, which examines the username of incoming
avatar requests.  There are special cases for ``change``, ``debug``, and
``statusClient``, which are not discussed here.  For all other usernames,
the botmaster is consulted, and if a slave with that name is configured, its
:class:`buildbot.buildslave.BuildSlave` instance is returned as the perspective.

Build Slaves
~~~~~~~~~~~~

At this point, the master-side BuildSlave object has a pointer to the remote,
slave-side Bot object in ``self.slave``, and the slave-side Bot object has a
reference to the master-side BuildSlave object in ``self.perspective``.

Bot methods
+++++++++++

The slave-side object has the following remote methods:


:meth:`remote_getCommands`
    Returns a list of ``(name, version)`` for all commands the slave recognizes

:meth:`remote_setBuilderList`
    Given a list of builders and their build directories, ensures that
    those builders, and only those builders, are running.  This can be
    called after the initial connection is established, with a new
    list, to add or remove builders.

    This method returns a dictionary of :class:`SlaveBuilder` objects - see below

:meth:`remote_print`
    Adds a message to the slave logfile

:meth:`remote_getSlaveInfo`
    Returns the contents of the slave's :file:`info/` directory. Also contains the keys


    ``environ``
        copy of the slaves environment
    ``system``
        OS the slave is running (extracted from pythons os.name)
    ``basedir``
        base directory where slave is running

:meth:`remote_getVersion`
    Returns the slave's version

BuildSlave methods
++++++++++++++++++

The master-side object has the following method:


:meth:`perspective_keepalive`
    Does nothing - used to keep traffic flowing over the TCP connection

Slave Builders
~~~~~~~~~~~~~~

.. py:class:: buildslave.bot.SlaveBuilder
.. py:class:: buildbot.process.builder.Builder
.. py:class:: buildbot.process.slavebuilder.SlaveBuilder

Each build slave has a set of builders which can run on it.  These are represented
by distinct classes on the master and slave, just like the BuildSlave and Bot objects
described above.

On the slave side, builders are represented as instances of the
:class:`buildslave.bot.SlaveBuilder` class.  On the master side, they are
represented by the :class:`buildbot.process.slavebuilder.SlaveBuilder` class.  The
following will refer to these as the slave-side and master-side SlaveBuilder
classes.  Each object keeps a reference to its opposite in ``self.remote``.

slave-side SlaveBuilder methods
+++++++++++++++++++++++++++++++

:meth:`remote_setMaster`
    Provides a reference to the master-side SlaveBuilder

:meth:`remote_print`
    Adds a message to the slave logfile; used to check round-trip connectivity

:meth:`remote_startBuild`
    Indicates that a build is about to start, and that any subsequent
    commands are part of that build

:meth:`remote_startCommand`
    Invokes a command on the slave side

:meth:`remote_interruptCommand`
    Interrupts the currently-running command

:meth:`remote_shutdown`
    Shuts down the slave cleanly

master-side SlaveBuilder methods
++++++++++++++++++++++++++++++++

The master side does not have any remotely-callable methods.

Setup
~~~~~

After the initial connection and trading of a mind (Bot) for an avatar
(BuildSlave), the master calls the Bot's :meth:`setBuilderList` method to set up
the proper slave builders on the slave side.  This method returns a reference to
each of the new slave-side SlaveBuilder objects.  Each of these is handed to the
corresponding master-side SlaveBuilder object.  This immediately calls the remote
:meth:`setMaster` method, then the :meth:`print` method.

Pinging
~~~~~~~

To ping a remote SlaveBuilder, the master calls the :meth:`print` method.

Building
~~~~~~~~

When a build starts, the msater calls the slave's :meth:`startBuild` method.
Each BuildStep instance will subsequently call the :meth:`startCommand` method,
passing a reference to itself as the ``stepRef`` parameter.  The
:meth:`startCommand` method returns immediately, and the end of the command is
signalled with a call to a method on the master-side BuildStep object.

master-side BuildStep methods
+++++++++++++++++++++++++++++

:meth:`remote_update`
    Update information about the running command.  See below for the format.

:meth:`remote_complete`
    Signal that the command is complete, either successfully or with a Twisted failure.

Updates from the slave are a list of individual update elements.  Each update
element is, in turn, a list of the form ``[data, 0]`` where the 0 is present
for historical reasons.  The data is a dictionary, with keys describing the
contents, e.g., ``header``, ``stdout``, or the name of a logfile.  If the
key is ``rc``, then the value is the exit status of the command.  No further
updates should be sent after an ``rc``.

