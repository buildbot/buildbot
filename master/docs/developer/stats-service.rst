.. _stats-service:

Statistics Service
==================

The statistic service (or stats service) is implemented in :mod:`buildbot.statistics.stats_service`.
Please see :bb:cfg:`stats-service` for more.

Here is a diagram demonstrating the working of the stats service:

.. image:: _images/stats-service.png

Stats Service
-------------

.. py:class:: StatsService

   An instance of this class functions as a :class:`BuildbotService`. The instance of the running
   service is initialized in the master configuration file (see :bb:cfg:`stats-service` for more).
   The running service is accessible everywhere in Buildbot via the :class:`BuildMaster`.
   The service is available at ``self.master.namedServices['<service-name>']``.
   It takes the following intialization arguments:

   * ``storage_backends``: A list of storage backends. These are instance of subclasses of :class:`StatsStorageBase`.
   * ``name``: The name of this service. This name can be used to access the running instance of this service using ``self.master.namedServices[name]``.

   Please see :bb:cfg:`stats-service` for examples.

   .. py:method:: checkConfig(self, storage_backends)

     :param storage_backends: A list of storage backends.

     This method is called automatically to verify that the list of storage backends contains instances
     of subclasses of :class:`StatsStorageBase`.

   .. py:method:: reconfigService(self, storage_backends)

     :param storage_backends: A list of storage backends.

     This mehtod is called automatically to reconfigure the running service.

   .. py:method:: registerConsumers(self)

      Internal method called to register all consumers (methods from Capture classes) to the MQ layer.

   .. py:method:: stopService(self)

      Internal method to stop the stats service and clean up.

   .. py:method:: removeConsumers(self)

      Internal method to stop and remove consumers from the MQ layer.

   .. py:method:: yieldMetricsValue(self, data_name, post_data, buildid)

      :param data_name: The name of the data being sent or storage.
      :param post_data: A dictionary of key value pair that is sent for storage.
      :type post_data: dict
      :param buildid: The integer build id of the current build. Obtainable in all ``BuildSteps``.

      This method should be called to post data that is not generated and stored as build-data in
      the database. This method generates the ``stats-yield-data`` event to the mq layer
      which is then consumed in :py:class:`postData`.

.. _storage-backend:


Storage backends
----------------

Storage backends are responsible for storing any stats-data sent to them.
A storage backend will generally be some sort of a database-server running on a machine.
(*Note*: This machine may be different from the one running :class:`BuildMaster`)

Data is captured according to the master config file and then, is sent to each of the storage backends provided by the master configuration (see :bb:cfg:`stats-service`).

Each storage backend has a Python client defined as part of :mod:`buildbot.statistics.storage_backends`
to aid in posting data by :class:`StatsService`

Currently, only `InfluxDB <http://influxdb.com>`_ is supported as a storage backend.

.. py:class:: StatsStorageBase

   A base class for all storage services

.. py:class:: InfluxStorageService

   `InfluxDB <http://influxdb.com>`_ is a distributed, time series database that employs a key-value pair storage system.

   This class is a Buildbot client to the InfluxDB storage backend.
   It is available in the configuration as ``stats.InfluxStorageService``
   It takes the following initialization arguments:

   * ``url``: The URL where the service is running.
   * ``port``: The port on which the service is listening.
   * ``user``: Username of a InfluxDB user.
   * ``password``: Password for ``user``.
   * ``db``: The name of database to be used.
   * ``captures``: A list of instances of subclasses of :py:class:`Capture`. This tells which stats are to be stored in this storage backend.
   * ``name=None``: (Optional) The name of this storage backend.

   .. py:method:: postStatsValue(self, post_data, series_name, context={})

      :param post_data: A dict of key-value pairs that is sent for storage. The keys of this dict can be thought of as columns in a database and the value is the data stored for that column.
      :type post_data: dict
      :param series_name: The name of the time-series for this statistic.
      :type series_name: str
      :param context: (Optional) Any other contextual information about the data. Dict of key-value pairs.
      :type context: dict

      This method constructs a dictionary of data to be sent to InfluxDB in the proper format and sends the data to the influxDB instance.


Capture Classes
---------------

Capture classes are used for declaring the data that needs to be sent to storage backends for storage.

.. py:class:: Capture

   A base class for all capture classes. Not to be used directly. Initlized with the following parameters:

   * ``routingKey``: (tuple) The routing key to be used by :class:`StatsService` to register consumers to the MQ lasyer for the subclass of this class.
   * ``callback``: The callback registered with the MQ layer for the consumer of a subclass of this class. Each subclass must provide a default callback for this purpose.

   .. py:method:: defaultContext(self, msg):

      A method for providing default context to the storage backends.

   .. py:method:: consumer(self, routingKey, msg):

      Raises ``NotImplementedError``. Each subclass of this method should implement its own consumer.
      The consumer, when calles (from the mq layer), receives the following arguments:

      * ``routingKey``: The routing key which was registered to the MQ layer. Same as the ``routingKey`` provided to instantiate this class.
      * ``msg``: The message that was sent by the producer.

.. py:class:: CaptureProperty

   The capture class to use for capturing build properties. It is available in the configuration as ``stats.CaptureProperty``

   It takes the following arguments:

   * ``builder_name``: The name of builder in which the property is recorded.
   * ``property_name``: The name of property needed to be recorded as a statistic.
   * ``callback=None``: The callback function that is used by ``CaptureProperty.consumer`` to post-process data before formatting it and sending it to the appropriate storage backends. A default callback is provided for this.

   **The default callback:**

     .. py:function:: default_callback

     Defined in ``CaptureProperty.__init__``. Receives:

     * ``props``: A dictionary of all build properties.
     * ``property_name``: Name of the build property to return.

     It returns property value for ``property_name``.

   .. py:method:: consumer(self, routingKey, msg)

   The consumer for this class. See :class:`Capture` for more.


.. py:class:: CaptureBuildTimes

   A base class for all Capture classes that deal with build times (start/end/duration). Not to be used directly. Initialized with:

   * ``builder_name``: The name of builder whose times are to be recorded.
   * ``callback``: The callback function that is used by subclass of this class to post-process data before formatting it and sending it to the appropriate storage backends. A default callback is provided for this. Each subclass must provide a deafault callback that is used in initialization of this class should the user not provide a callback.

   :py:meth:`consumer(self, routingKey, msg)`

     The consumer for all subclasses of this class. See :class:`Capture` for more.
     **Note**: This consumer requires all subclasses to implement:

     * ``self._time_type`` (property): A string used as a key in ``post_data`` sent to sotrage services.
     * ``self.retValParams(msg)`` (method): A method that takes in the ``msg`` this consumer gets and returns a list of arguments for the capture callback.


.. py:class:: CaptureBuildStartTime

   A capture class for capturing build start times. Takes the following arguments:

   * ``builder_name``: The name of builder whose times are to be recorded.
   * ``callback=None``: The callback function for this class. See :class:`CaptureBuildTimes` for more.

   **The default callback:**

      .. py:function:: default_callback

      Defined in ``CaptureBuildStartTime.__init__``. It returns the start time in ISO format. It takes one argument:

      * ``start_time``: A python datetime object that denotes the build start time.

   .. py:method:: retValParams(self, msg)

   Returns a list containing one Python datetime object (start time) from ``msg`` dictionary.


.. py:class:: CaptureBuildEndTime

   A capture class for capturing build end times. Takes the following arguments:

   * ``builder_name``: The name of builder whose times are to be recorded.
   * ``callback=None``: The callback function for this class. See :class:`CaptureBuildTimes` for more.

   **The default callback:**

      .. py:function:: default_callback

      Defined in ``CaptureBuildEndTime.__init__``. It returns the end time in ISO format. It takes one argument:

      * ``end_time``: A python datetime object that denotes the build end time.

   .. py:method:: retValParams(self, msg)

   Returns a list containing two Python datetime object (start time and end time) from ``msg`` dictionary.


.. py:class:: CaptureBuildDuration

   A capture class for capturing build duration. Takes the following arguments:

   * ``builder_name``: The name of builder whose times are to be recorded.
   * ``report_in='seconds'``: Can be one of three: ``'seconds'``, ``'minutes'``, or ``'hours'``. This is the units in which the build time will be reported.
   * ``callback=None``: The callback function for this class. See :class:`CaptureBuildTimes` for more.

   **The default callback:**

      .. py:function:: default_callback

      Defined in ``CaptureBuildDuration.__init__``. It returns the duration of the build as per the ``report_in`` argument. It receives:
      * ``start_time``: A python datetime object that denotes the build start time.
      * ``end_time``: A python datetime object that denotes the build end time.

   .. py:method:: retValParams(self, msg)

   Returns a list containing one Python datetime object (end time) from ``msg`` dictionary.


.. py:class:: CaptureData

   A capture class for capturing arbitrary data that is not stored as build-data. See :meth:`yieldMetricsValue` for more. Takes the following arguments:

   * ``data_name``: The name of data to be captured. Same as in :meth:`yieldMetricsValue`.
   * ``builder_name``: The name of builder whose times are to be recorded.
   * ``callback=None``: The callback function for this class. See :class:`CaptureBuildTimes` for more.

   **The default callback:**

      The default callback takes a value ``x`` and return it without changing. As such, ``x`` acts as the ``post_data`` sent to the storage backends.

   .. py:method:: consumer(self, routingKey, msg)

   The consumer for this class. See :class:`Capture` for more.
