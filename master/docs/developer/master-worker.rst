Master-Worker API
=================

This section describes the master-worker interface.

Connection
----------

The interface is based on Twisted's Perspective Broker, which operates over TCP
connections.

The worker connects to the master, using the parameters supplied to
:command:`buildslave create-slave`.  It uses a reconnecting process with an
exponential backoff, and will automatically reconnect on disconnection.

Once connected, the worker authenticates with the Twisted Cred (newcred)
mechanism, using the username and password supplied to :command:`buildslave
create-slave`.  The *mind* is the worker bot instance (class
:class:`buildslave.bot.Bot`).

On the master side, the realm is implemented by
:class:`buildbot.master.Dispatcher`, which examines the username of incoming
avatar requests.  There are special cases for ``change``, ``debug``, and
``statusClient``, which are not discussed here.  For all other usernames,
the botmaster is consulted, and if a worker with that name is configured, its
:class:`buildbot.worker.Worker` instance is returned as the perspective.

Workers
-------

At this point, the master-side Worker object has a pointer to the remote,
worker-side Bot object in its ``self.worker``, and the worker-side Bot object has
a reference to the master-side Worker object in its ``self.perspective``.

Bot methods
~~~~~~~~~~~

The worker-side Bot object has the following remote methods:

:meth:`~buildslave.bot.Bot.remote_getCommands`
    Returns a list of ``(name, version)`` for all commands the worker recognizes

:meth:`~buildslave.bot.Bot.remote_setBuilderList`
    Given a list of builders and their build directories, ensures that
    those builders, and only those builders, are running.  This can be
    called after the initial connection is established, with a new
    list, to add or remove builders.

    This method returns a dictionary of :class:`SlaveBuilder` objects - see below

:meth:`~buildslave.bot.Bot.remote_print`
    Adds a message to the worker logfile

:meth:`~buildslave.bot.Bot.remote_getSlaveInfo`
    Returns the contents of the worker's :file:`info/` directory. This also
    contains the keys

    ``environ``
        copy of the workers environment
    ``system``
        OS the worker is running (extracted from Python's os.name)
    ``basedir``
        base directory where worker is running
    ``numcpus``
        number of CPUs on the worker, either as configured or as detected (since ``buildbot-slave`` version 0.9.0)

:meth:`~buildslave.bot.Bot.remote_getVersion`
    Returns the worker's version

Worker methods
~~~~~~~~~~~~~~

The master-side object has the following method:

:meth:`~buildbot.worker.Worker.perspective_keepalive`
    Does nothing - used to keep traffic flowing over the TCP connection

Setup
-----

After the initial connection and trading of a mind (Bot) for an avatar
(BuildSlave), the master calls the Bot's :meth:`setBuilderList` method to set
up the proper builders on the worker side.  This method returns a
reference to each of the new worker-side :class:`~buildslave.bot.SlaveBuilder`
objects, described below.  Each of these is handed to the corresponding
master-side :class:`~buildbot.process.workerforbuilder.WorkerForBuilder` object.

This immediately calls the remote :meth:`setMaster` method, then the
:meth:`print` method.

Pinging
-------

To ping a remote SlaveBuilder, the master calls its :meth:`print` method.

Building
--------

When a build starts, the master calls the worker's :meth:`startBuild` method.
Each BuildStep instance will subsequently call the :meth:`startCommand` method,
passing a reference to itself as the ``stepRef`` parameter.  The
:meth:`startCommand` method returns immediately, and the end of the command is
signalled with a call to a method on the master-side BuildStep object.

Slave Builders
--------------

Each worker has a set of builders which can run on it.  These are
represented by distinct classes on the master and worker, just like the
BuildSlave and Bot objects described above.

On the worker side, builders are represented as instances of the
:class:`buildslave.bot.SlaveBuilder` class.  On the master side, they are
represented by the :class:`buildbot.process.workerforbuilder.SlaveBuilder` class.
The identical names are a source of confusion.  The following will refer to
these as the worker-side and master-side SlaveBuilder classes.  Each object
keeps a reference to its opposite in ``self.remote``.

Slave-Side SlaveBuilder Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:meth:`~buildslave.bot.SlaveBuilder.remote_setMaster`
    Provides a reference to the master-side SlaveBuilder

:meth:`~buildslave.bot.SlaveBuilder.remote_print`
    Adds a message to the worker logfile; used to check round-trip connectivity

:meth:`~buildslave.bot.SlaveBuilder.remote_startBuild`
    Indicates that a build is about to start, and that any subsequent
    commands are part of that build

:meth:`~buildslave.bot.SlaveBuilder.remote_startCommand`
    Invokes a command on the worker side

:meth:`~buildslave.bot.SlaveBuilder.remote_interruptCommand`
    Interrupts the currently-running command

:meth:`~buildslave.bot.SlaveBuilder.remote_shutdown`
    Shuts down the worker cleanly

Master-side WorkerForBuilder Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The master side does not have any remotely-callable methods.

Commands
--------

Actual work done by the worker is represented on the master side by a
:class:`buildbot.process.remotecommand.RemoteCommand` instance.

The command instance keeps a reference to the worker-side
:class:`buildslave.bot.SlaveBuilder`, and calls methods like
:meth:`~buildslave.bot.SlaveBuilder.remote_startCommand` to start new commands.
Once that method is called, the :class:`~buildslave.bot.SlaveBuilder` instance
keeps a reference to the command, and calls the following methods on it:

Master-Side RemoteCommand Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:meth:`~buildbot.process.remotecommand.RemoteCommand.remote_update`
    Update information about the running command.  See below for the format.

:meth:`~buildbot.process.remotecommand.RemoteCommand.remote_complete`
    Signal that the command is complete, either successfully or with a Twisted failure.

.. _master-worker-updates:

Updates
-------

Updates from the worker, sent via
:meth:`~buildbot.process.remotecommand.RemoteCommand.remote_update`, are a list of
individual update elements.  Each update element is, in turn, a list of the
form ``[data, 0]`` where the 0 is present for historical reasons.  The data is
a dictionary, with keys describing the contents.  The updates are handled by
:meth:`~buildbot.process.remotecommand.RemoteCommand.remote_update`.

Updates with different keys can be combined into a single dictionary or
delivered sequentially as list elements, at the worker's option.

To summarize, an ``updates`` parameter to
:meth:`~buildbot.process.remotecommand.RemoteCommand.remote_update` might look like
this::

    [
        [ { 'header' : 'running command..' }, 0 ],
        [ { 'stdout' : 'abcd', 'stderr' : 'local modifications' }, 0 ],
        [ { 'log' : ( 'cmd.log', 'cmd invoked at 12:33 pm\n' ) }, 0 ],
        [ { 'rc' : 0 }, 0 ],
    ]

Defined Commands
~~~~~~~~~~~~~~~~

The following commands are defined on the workers.

.. _shell-command-args:

shell
.....

Runs a shell command on the worker.  This command takes the following arguments:

``command``

    The command to run.  If this is a string, will be passed to the system
    shell as a string.  Otherwise, it must be a list, which will be
    executed directly.

``workdir``

    Directory in which to run the command, relative to the builder dir.

``env``

    A dictionary of environment variables to augment or replace the
    existing environment on the worker.  In this dictionary, ``PYTHONPATH``
    is treated specially: it should be a list of path components, rather
    than a string, and will be prepended to the existing Python path.

``initial_stdin``

    A string which will be written to the command's standard input before
    it is closed.

``want_stdout``

    If false, then no updates will be sent for stdout.

``want_stderr``

    If false, then no updates will be sent for stderr.

``usePTY``

    If true, the command should be run with a PTY (POSIX only).  This
    defaults to the value specified in the worker's ``buildbot.tac``.

``not_really``

    If true, skip execution and return an update with rc=0.

``timeout``

    Maximum time without output before the command is killed.

``maxTime``

    Maximum overall time from the start before the command is killed.

``logfiles``

    A dictionary specifying logfiles other than stdio.  Keys are the logfile
    names, and values give the workdir-relative filename of the logfile.  Alternately,
    a value can be a dictionary; in this case, the dictionary must have a ``filename``
    key specifying the filename, and can also have the following keys:

    ``follow``

        Only follow the file from its current end-of-file, rather that starting
        from the beginning.

``logEnviron``

    If false, the command's environment will not be logged.

The ``shell`` command sends the following updates:

``stdout``
    The data is a bytestring which represents a continuation of the stdout
    stream.  Note that the bytestring boundaries are not necessarily aligned
    with newlines.

``stderr``
    Similar to ``stdout``, but for the error stream.

``header``
    Similar to ``stdout``, but containing data for a stream of
    Buildbot-specific metadata.

``rc``
    The exit status of the command, where -- in keeping with UNIX tradition --
    0 indicates success and any nonzero value is considered a failure.  No
    further updates should be sent after an ``rc``.

``log``
    This update contains data for a logfile other than stdio.  The data
    associated with the update is a tuple of the log name and the data for that
    log.  Note that non-stdio logs do not distinguish output, error, and header
    streams.

uploadFile
..........

Upload a file from the worker to the master.  The arguments are

``workdir``

    The base directory for the filename, relative to the builder's basedir.

``workersrc``

    Name of the filename to read from., relative to the workdir.

``writer``

    A remote reference to a writer object, described below.

``maxsize``

    Maximum size, in bytes, of the file to write.  The operation will fail if
    the file exceeds this size.

``blocksize``

    The block size with which to transfer the file.

``keepstamp``

    If true, preserve the file modified and accessed times.

The worker calls a few remote methods on the writer object.  First, the
``write`` method is called with a bytestring containing data, until all of the
data has been transmitted.  Then, the worker calls the writer's ``close``,
followed (if ``keepstamp`` is true) by a call to ``upload(atime, mtime)``.

This command sends ``rc`` and ``stderr`` updates, as defined for the ``shell``
command.

uploadDirectory
...............

Similar to ``uploadFile``, this command will upload an entire directory to the
master, in the form of a tarball.  It takes the following arguments:

``workdir``
``workersrc``
``writer``
``maxsize``
``blocksize``

    See ``uploadFile``

``compress``

    Compression algorithm to use -- one of ``None``, ``'bz2'``, or ``'gz'``.

The writer object is treated similarly to the ``uploadFile`` command, but after
the file is closed, the worker calls the master's ``unpack`` method with no
arguments to extract the tarball.

This command sends ``rc`` and ``stderr`` updates, as defined for the ``shell``
command.

downloadFile
............

This command will download a file from the master to the worker.  It takes the
following arguments:

``workdir``

    Base directory for the destination filename, relative to the builder basedir.

``workerdest``

    Filename to write to, relative to the workdir.

``reader``

    A remote reference to a reader object, described below.

``maxsize``

    Maximum size of the file.

``blocksize``

    The block size with which to transfer the file.

``mode``

    Access mode for the new file.

The reader object's ``read(maxsize)`` method will be called with a maximum
size, which will return no more than that number of bytes as a bytestring.  At
EOF, it will return an empty string.  Once EOF is received, the worker will call
the remote ``close`` method.

This command sends ``rc`` and ``stderr`` updates, as defined for the ``shell``
command.

mkdir
.....

This command will create a directory on the worker.  It will also create any
intervening directories required.  It takes the following argument:

``dir``

    Directory to create.

The ``mkdir`` command produces the same updates as ``shell``.

rmdir
.....

This command will remove a directory or file on the worker.  It takes the following arguments:

``dir``

    Directory to remove.

``timeout``
``maxTime``

    See ``shell``, above.

The ``rmdir`` command produces the same updates as ``shell``.

cpdir
.....

This command will copy a directory from place to place on the worker.  It takes the following
arguments:

``fromdir``

    Source directory for the copy operation, relative to the builder's basedir.

``todir``

    Destination directory for the copy operation, relative to the builder's basedir.

``timeout``
``maxTime``

    See ``shell``, above.

The ``cpdir`` command produces the same updates as ``shell``.

stat
....

This command returns status information about a file or directory.  It takes a
single parameter, ``file``, specifying the filename relative to the builder's
basedir.

It produces two status updates:

``stat``

    The return value from Python's ``os.stat``.

``rc``

    0 if the file is found, otherwise 1.

glob
....

This command finds all pathnames matching a specified pattern that uses shell-style wildcards.
It takes a single parameter, ``path``, specifying the pattern to pass to Python's
``glob.glob`` function.

It produces two status updates:

``files``

    The list of matching files returned from ``glob.glob``

``rc``

    0 if the ``glob.glob`` does not raise exception, otherwise 1.

listdir
.......

This command reads the directory and returns the list with directory contents. It
takes a single parameter, ``dir``, specifying the directory relative to builder's basedir.

It produces two status updates:

``files``

    The list of files in the directory returned from ``os.listdir``

``rc``

    0 if the ``os.listdir`` does not raise exception, otherwise 1.

Source Commands
...............

The source commands (``bk``, ``cvs``, ``darcs``, ``git``, ``repo``, ``bzr``,
``hg``, ``p4``, ``p4sync``, and ``mtn``) are deprecated.  See the docstrings in
the source code for more information.
