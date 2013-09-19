Protocols
=========

To exchange information over the network between master and slave we need to use
protocol.

:class:`Listener` and :class:`Connection` provide interfaces to implement
wrappers around protocol specific calls, so other classes which use them no need
to know about protocol calls or handle protocol specific exceptions.

.. py:class Listener(master)

    :param master: buildbot.master.BuildMaster instance

    Responsible for spawning Connection instances and updating registrations

.. py:class Connection(master, buildslave, mind)

    :param master: buildbot.master.BuildMaster instance
    :param buildslave: buildbot.buildslave.base.BuildSlave instace
    :param mind: represents client object

    Represents connection to single slave

    .. py:method:: notifyOnDisconnect(cb)

        :param cb: callback
        :returns: Deferred

        Register a callback to be called if slave gets disconnected

    .. py:method:: notifyDisconnected()

        Execute callback set by notifyOnDisconnect

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
        :returns: Deferred

        Take list with wanted builders and send them to slave, return list with
        created builders
