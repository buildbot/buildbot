Build Workers
=============

.. py:module:: buildbot.buildworker.base

The :py:class:`BuildWorker` class represents a buildworker, which may or may not be connected to the master.
Instances of this class are created directly in the Buildbot configuration file.

BuildWorker
-----------

.. py:class:: BuildWorker

    .. py:attribute:: bulidworkerid

        The ID of this buildworker in the database.
