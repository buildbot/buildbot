Protocols
=========

To exchange information over the network between master and slave we need to use
protocol.

:class:`Listener` and :class:`Connection` provide interfaces to implement
wrappers around protocol specific calls, so other classes which use them no need
to know about protocol calls or handle protocol specific exceptions.

.. py:class Listener(master)

    :param master: :py:class:`buildbot.master.BuildMaster` instance

    Responsible for spawning Connection instances and updating registrations.
    Protocol-specific subclasses are instantiated with protocol-specific
    parameters by the buildmaster during startup.

.. py:class Connection(master, buildslave, mind)

    Represents connection to single slave

    .. py:method:: notifyOnDisconnect(cb)

        :param cb: callback
        :returns: :py:class:`buildbot.util.subscriptions.Subscription`

        Register a callback to be called if slave gets disconnected

    .. py:method:: loseConnection()

        Close connection

    .. py:method:: remotePrint(message)

        :param message: message for slave
        :type message: string
        :returns: Deferred

        Print message to slave log file

    .. py:method:: remoteGetSlaveInfo()

        :returns: Deferred

        Get slave information, commands and version, put them in dictonary
        then return back

    .. py:method:: remoteSetBuilderList(builders)

        :param builders: list with wanted builders
        :type builders: List
        :returns: Deferred containing PB references XXX

        Take list with wanted builders and send them to slave, return list with
        created builders

    .. py:method:: remoteStartCommand(remoteCommand, builderName, commandId, commandName, args)

        :param remoteCommand: :py:class:`~buildbot.process.remotecommand.RemoteCommand` instance
        :param builderName: self explanatory
        :type builderName: string
        :param commandId: command number
        :type commandId: string
        :param commandName: command which will be executed on slave
        :type commandName: string
        :param args: arguments for that command
        :type args: List
        :returns: Deferred

        Start command on slave

    .. py:method:: remoteShutdown()

        :returns: Deferred

        Shutdown the slave, causing its process to halt permanently.

    .. py:method:: remoteStartBuild(builderName)

        :param builderName name of the builder for which the build is starting
        :returns: Deferred

        Just starts build

    .. py:method:: remoteInterruptCommand(commandId, why)

        :param commandId: command number
        :type commandId: string
        :param why: reason to interrupt
        :type why: string
        :returns: Deferred

        Interrupt command with given CommandID on slave, print reason "why" to
        slave logs
