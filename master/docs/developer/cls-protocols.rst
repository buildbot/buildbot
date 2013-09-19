Protocols
=========

To exchange information over the network between master and slave we need to use
protocol.

Perspective Broker(PB) is a RPC protocol which provides remotely-invokable
methods, twisted.cred authentication layer, transparent, controllable object
serialization etc.
http://twistedmatrix.com/documents/current/core/howto/pb-intro.html

:class:`Listener` and :class:`Connection` provide interfaces to implement
wrappers around protocol specific calls, so other classes which use them no need
to know about protocol calls or handle protocol specific exceptions.

Perspective Broker
~~~~~~~~~~~~~~~~~~

.. py:class Listener(master)

    :param master: buildbot.master.BuildMaster instance

    Responsible for spawning Connection instances and updating registrations
    for pbmanager

    .. py:method:: updateRegistration(username, password, portStr)

        :param username: slave name
        :type username: string
        :param password: slave password
        :type password: string
        :param portStr: port string in twisted strports format
        :type portStr: string
        :returns: pbmanager.Registration

        Update registration for pbmanager. This methods checks that username
        exists in self._registrations and update it registration if password or
        portStr was changed

    .. py:method:: _getPerspective(mind, buildslaveName)

        :param mind: represents client object
        :param buildslaveName: slave name
        :type buildslaveName: string
        :returns: buildslave.protocols.pb.Connection

        Sets TCP keepalive time for transport and returns new Connection instance
        for given buildslaveName

.. py:class Connection(master, buildslave, mind)

    :param master: buildbot.master.BuildMaster instance
    :param buildslave: buildbot.buildslave.base.BuildSlave instace
    :param mind: represents client object

    Represents connection to single PB slave

    .. py:attribute:: keepalive_timer

        timer which calls self.doKeepalive each self.keepalive_interval seconds

    .. py:attribute:: keepalive_interval

        Contain time interval in seconds

    .. py:method:: attached(mind)

        :param mind: represents client object
        :returns: self

        Start keepalive timer and attache itself to BuildSlave instance

    .. py:method:: detached(mind)

        :param mind: represents client object

        Stop keepalive timer and call callback setted by notifyDisconnect()

    .. py:method:: loseConnection()

        Stop keepalive timer and disconnect

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
        :returns: Deferred

        Take list with wanted builders and send them to slave, return list with
        created builders

    .. py:method:: perspective_keepalive()

        # Do we need this?

    .. py:method:: perspective_shutdown()

        # Do we need this?

    .. py:method:: startCommands(RCInstance, builder_name, commandID, remote_command, args)

        :param RCInstance: buildbot.process.buildstep.RemoteCommand instance
        :param builder_name: self explanatory
        :type builder_name: string
        :param commandID: command number
        :type commandID: string
        :param remote_command: command which will be executed on slave
        :type remote_command: string
        :param args: arguments for that command
        :type args: List
        :returns: Deferred

        Start command on slave

    .. py:method:: doKeepalive()

        :returns: Deferred

        Just print message "keepalive" to slave log file

    .. py:method:: remoteShutdown(buildslave)

        :param buildslave: buildbot.buildslave.base.BuildSlave instance
        :returns: Deferred

        Shutdown slave, "buildslave" required to shutdown old slaves(saved for
        backward compatability)

    .. py:method:: remoteStartBuild()

        :returns: Deferred

        Just starts build

    .. py:method:: stopKeepaliveTimer()

        Stop keepalive timer

    .. py:method:: startKeepaliveTimer()

        Start keepalive timer

    .. py:method:: remoteInterruptCommand(commandID, why)

        :param commandID: command number
        :type commandID: string
        :param why: reason to interrupt
        :type why: string
        :returns: Deferred

        Interrupt command with given CommandID on slave, print reason "why" to
        slave logs
