.. _stats-service:

Statistics Service
==================

The statistic service (or stats service) is implemented in :mod:`buildbot.statistics.stats_service`.
Please see :bb:cfg:`stats-service` for more.

Here is a diagram demonstrating the working of the stats service:

.. image:: _images/stats-service.*

Stats Service
-------------

.. py:class:: StatsService

   An instance of this class functions as a twisted service.
   The running service is accessible everywhere in Buildbot via the :class:`BuildMaster`.
   The service is available at ``master.stats_service``

   .. py:method:: postProperties(properties, builder_name)

      :param properties: An instance of :class:`buildbot.process.Properties`
      :param builder_name: The name of the builder whose properties are being sent to
                           the storage backends.
      :returns: Deferred

      This method is called at the end of each build. It filters out which build
      properties to send to :class:`postStatsValue` of python clients of storage backends
      (:ref:`storage-backend`) which then send these properties for storage.
