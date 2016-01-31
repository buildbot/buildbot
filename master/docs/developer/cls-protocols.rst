Protocols
=========

To exchange information over the network between master and worker we need to use
protocol.

:mod:`buildbot.worker.protocols.base` provide interfaces to implement
wrappers around protocol specific calls, so other classes which use them do not need
to know about protocol calls or handle protocol specific exceptions.

.. py:module:: buildbot.worker.protocols.base


.. py:class:: Listener(master)

    :param master: :py:class:`buildbot.master.BuildMaster` instance

    Responsible for spawning Connection instances and updating registrations.
    Protocol-specific subclasses are instantiated with protocol-specific
    parameters by the buildmaster during startup.

.. py:class:: Connection(master, worker)

    Represents connection to single worker

    .. py:attribute:: proxies

        Dictionary containing mapping between ``Impl`` classes and ``Proxy`` class for this protocol
        This may be overridden by subclass to declare its proxy implementations

    .. py:method:: createArgsProxies(args)

        :returns: shallow copy of args dictionary with proxies instead of impls

        Helper method that will use :attr:`proxies`, and replace ``Impl`` objects by specific ``Proxy`` counterpart.

    .. py:method:: notifyOnDisconnect(cb)

        :param cb: callback
        :returns: :py:class:`buildbot.util.subscriptions.Subscription`

        Register a callback to be called if worker gets disconnected

    .. py:method:: loseConnection()

        Close connection

    .. py:method:: remotePrint(message)

        :param message: message for worker
        :type message: string
        :returns: Deferred

        Print message to worker log file

    .. py:method:: remoteGetWorkerInfo()

        :returns: Deferred

        Get worker information, commands and version, put them in dictonary
        then return back

    .. py:method:: remoteSetBuilderList(builders)

        :param builders: list with wanted builders
        :type builders: List
        :returns: Deferred containing PB references XXX

        Take list with wanted builders and send them to worker, return list with
        created builders

    .. py:method:: remoteStartCommand(remoteCommand, builderName, commandId, commandName, args)

        :param remoteCommand: :py:class:`~buildbot.worker.protocols.base.RemoteCommandImpl` instance
        :param builderName: self explanatory
        :type builderName: string
        :param commandId: command number
        :type commandId: string
        :param commandName: command which will be executed on worker
        :type commandName: string
        :param args: arguments for that command
        :type args: List
        :returns: Deferred

        Start command on worker

    .. py:method:: remoteShutdown()

        :returns: Deferred

        Shutdown the worker, causing its process to halt permanently.

    .. py:method:: remoteStartBuild(builderName)

        :param builderName name of the builder for which the build is starting
        :returns: Deferred

        Just starts build

    .. py:method:: remoteInterruptCommand(builderName, commandId, why)

        :param builderName: self explanatory
        :type builderName: string
        :param commandId: command number
        :type commandId: string
        :param why: reason to interrupt
        :type why: string
        :returns: Deferred

        Interrupt the command executed on builderName with given commandId on worker, print reason "why" to
        worker logs

Following classes are describing the worker -> master part of the protocol.

In order to support old workers, we must make sure we do not change the current pb protocol.
This is why we implement a ``Impl vs Proxy`` methods.
All the objects that are referenced from the workers for remote calls have an ``Impl`` and a ``Proxy`` base classes in this module.

``Impl`` classes are subclassed by buildbot master, and implement the actual logic for the protocol api.
``Proxy`` classes are implemented by the worker/master protocols, and implements the demux and de-serialization of protocol calls.

On worker sides, those proxy objects are replaced by a proxy object having a single method to call master side methodss:

.. py:class:: workerProxyObject()

    .. py:method:: callRemote(message, *args, **kw)

        calls the method ``"remote_" + message`` on master side

.. py:class:: RemoteCommandImpl()

    Represents a RemoteCommand status controller

    .. py:method:: remote_update(updates)

        :param updates: dictionary of updates

        Called when the workers has updates to the current remote command

        possible keys for updates are:

        * ``stdout``: Some logs where captured in remote command's stdout. value: ``<data> as string``

        * ``stderr``: Some logs where captured in remote command's stderr. value: ``<data> as string``

        * ``header``: remote command's header text. value: ``<data> as  string``

        * ``log``: one of the watched logs has received some text. value: ``(<logname> as string, <data> as string)``

        * ``rc``: Remote command exited with a return code. value: ``<rc> as integer``

        * ``elapsed``: Remote command has taken <elapsed> time. value: ``<elapsed seconds> as float``

        * ``stat``: sent by the ``stat`` command with the result of the os.stat, converted to a tuple. value: ``<stat> as tuple``

        * ``files``: sent by the ``glob`` command with the result of the glob.glob. value: ``<files> as list of string``

        * ``got_revision``: sent by the source commands with the revision checked out. value: ``<revision> as string``

        * ``repo_downloaded``: sent by the ``repo`` command with the list of patches downloaded by repo. value: ``<downloads> as list of string``


    .. :py:method:: remote_complete(failure=None)

        :param failure: copy of the failure if any

            Called by the worker when the command is complete.


.. py:class:: FileWriterImpl()

    Class used to implement data transfer between worker and master

    .. :py:method:: remote_write(data)

        :param data: data to write

        data needs to be written on master side

    .. :py:method:: remote_utime(accessed_modified)

        :param accessed_modified: modification times

        called with value of the modification time to update on master side

    .. :py:method:: remote_unpack()

        Called when master should start to unpack the tarball sent via command ``uploadDirectory``

    .. :py:method:: remote_close()

        Called when master should close the file


.. py:class:: FileReaderImpl(object)

    .. py:method:: remote_read(maxLength)

        :param maxLength: maximum length of the data to send
        :returns: data read

        called when worker needs more data

    .. py:method:: remote_close()

        Called when master should close the file
