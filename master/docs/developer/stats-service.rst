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

.. _storage-backend:


Storage backends
----------------

Storage backends are responsible for storing any stats-data sent to them.
A storage backend will generally be some sort of a database-server running on a machine.
(*Note*: This machine may be different from the one running :class:`BuildMaster`)

Build data is sent to each of the storage backends provided by the master configuration (see :bb:cfg:`stats-service`).
This data is then filtered for the statistics that the user wants to be stored.

Each storage backend has a Python client defined as part of :mod:`buildbot.statistics.storage_backends`
to aid in posting and retrieving data by :class:`StatsService`

Currently, only `InfluxDB <http://influxdb.com>` is supported as a storage backend.

.. py:class:: StatsStorageBase

   A base class for all storage services

.. py:class:: InfluxStorageService

   `InfluxDB <http://influxdb.com>` is a distributed, time series database that employs a key-value pair storage system.

   This class is a Buildbot client to the InfluxDB storage backend.
   It is available in the configuration as ``stats.InfluxStorageService``
   It takes the following initialization arguments:

   * ``url``: The URL where the service is running.
   * ``port``: The port on which the service is listening.
   * ``user``: Username of a InfluxDB user.
   * ``password``: Password for ``user``.
   * ``db``: The name of database to be used.
   * ``stats``: A list of :py:class:`CaptureProperty`. This tells which stats are to be stored in this storage backend.
   * ``name=None``: (Optional) The name of this storage backend.

   .. py:method:: postStatsValue(self, name, value, series_name, context={})

      :param name: The name of the statistic being sent for storage.
      :param value: Value to be stored.
      :param series_name: The name of the time-series for this statistic.
      :type series_name: str
      :param context: (Optional) Any other contextual information about name-value pair.
      :type context: dict

      This method constructs a dictionary of data to be sent to InfluxDB in the proper format and sends the data to the
      influxDB instance.
