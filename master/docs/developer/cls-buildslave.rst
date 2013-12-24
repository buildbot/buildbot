Build Slaves
============

.. py:module:: buildbot.buildslave.base

The :py:class:`BuildSlave` class represents a buildslave, which may or may not be connected to the master.
Instances of this class are created directly in the Buildbot configuration file.

BuildSlave
----------

.. py:class:: BuildSlave

    .. py:attribute:: bulidslaveid

        The ID of this buildslave in the database.
