BaseScheduler
-------------

.. py:module:: buildbot.schedulers.base

.. py:class:: BaseScheduler

    This is the base class for all Buildbot schedulers.
    See :ref:`Writing-Schedulers` for information on writing new schedulers.

    .. py:method:: __init__(name, builderNames, properties={}, codebases={'':{}})

        :param name: (positional) the scheduler name
        :param builderName: (positional) a list of builders, by name, for which this scheduler can queue builds
        :param properties: a dictionary of properties to be added to queued builds
        :param codebases: the codebase configuration for this scheduler (see user documentation)

        Initializes a new scheduler.

    The scheduler configuration parameters, and a few others, are available as attributes:

    .. py:attribute:: name

        This scheduler's name.

    .. py:attribute:: builderNames

        :type: list

        Builders for which this scheduler can queue builds.

    .. py:attribute:: codebases

        :type: dict

        The codebase configuration for this scheduler.

    .. py:attribute:: properties

        :type: Properties instance

        Properties that this scheduler will attach to queued builds.
        This attribute includes the ``scheduler`` property.

    .. py:attribute:: schedulerid

        :type: integer

        The ID of this scheduler in the ``schedulers`` table.

    Subclasses can consume changes by implementing :py:meth:`gotChange` and calling :py:meth:`startConsumingChanges` from :py:meth:`startActivity`.

    .. py:method:: startConsumingChanges(self, fileIsImportant=None, change_filter=None, onlyImportant=False)

        :param fileIsImportant: a callable provided by the user to distinguish important and unimportant changes
        :type fileIsImportant: callable
        :param change_filter: a filter to determine which changes are even considered by this scheduler, or ``None`` to consider all changes
        :type change_filter: :py:class:`buildbot.changes.filter.ChangeFilter` instance
        :param onlyImportant: If True, only important changes, as specified by fileIsImportant, will be added to the buildset.
        :type onlyImportant: boolean
        :return: Deferred

        Subclasses should call this method when becoming active in order to receive changes.
        The parent class will take care of filtering the changes (using ``change_filter``) and (if ``fileIsImportant`` is not None) classifying them.

    .. py:method:: gotChange(change, important)

        :param buildbot.changes.changes.Change change: the new change
        :param boolean important: true if the change is important
        :return: Deferred

        This method is called when a change is received.
        Schedulers which consume changes should implement this method.

        If the ``fileIsImportant`` parameter to ``startConsumingChanges`` was None, then all changes are considered important.
        It is guaranteed that the ``codebase`` of the change is one of the scheduler's codebase.

        .. note::

            The :py:class:`buildbot.changes.changes.Change` instance will instead be a change resource in later versions.

    The following methods are available for subclasses to queue new builds.
    Each creates a new buildset with a build request for each builder.

    .. py:method:: addBuildsetForSourceStamps(self, sourcestamps=[], waited_for=False, reason='', external_idstring=None, properties=None, builderNames=None)

        :param list sourcestamps: a list of full sourcestamp dictionaries or sourcestamp IDs
        :param boolean waited_for: if true, this buildset is being waited for (and thus should continue during a clean shutdown)
        :param string reason: reason for the build set
        :param string external_idstring: external identifier for the buildset
        :param properties: properties - in addition to those in the scheduler configuration - to include in the buildset
        :type properties: :py:class:`~buildbot.process.properties.Properties` instance
        :param list builderNames: a list of builders for the buildset, or None to use the scheduler's configured ``builderNames``
        :returns: (buildset ID, buildrequest IDs) via Deferred

        Add a buildset for the given source stamps.
        Each source stamp must be specified as a complete source stamp dictionary (with keys ``revision``, ``branch``, ``project``, ``repository``, and ``codebase``), or an integer ``sourcestampid``.

        The return value is a tuple.
        The first tuple element is the ID of the new buildset.
        The second tuple element is a dictionary mapping builder name to buildrequest ID.

    .. py:method:: addBuildsetForSourceStampsWithDefaults(reason, sourcestamps, waited_for=False, properties=None, builderNames=None)

        :param string reason: reason for the build set
        :param list sourcestamps: partial list of source stamps to build
        :param boolean waited_for: if true, this buildset is being waited for (and thus should continue during a clean shutdown)
        :param dict properties: properties - in addition to those in the scheduler configuration - to include in the buildset
        :type properties: :py:class:`~buildbot.process.properties.Properties` instance
        :param list builderNames: a list of builders for the buildset, or None to use the scheduler's configured ``builderNames``
        :returns: (buildset ID, buildrequest IDs) via Deferred, as for :py:meth:`addBuildsetForSourceStamps`

        Create a buildset based on the supplied sourcestamps, with defaults applied from the scheduler's configuration.

        The ``sourcestamps`` parameter is a list of source stamp dictionaries, giving the required parameters.
        Any unspecified values, including sourcestamps from unspecified codebases, will be filled in from the scheduler's configuration.
        If ``sourcestamps`` is None, then only the defaults will be used.
        If ``sourcestamps`` includes sourcestamps for codebases not configured on the scheduler, they will be included anyway, although this is probably a sign of an incorrect configuration.

    .. py:method:: addBuildsetForChanges(waited_for=False, reason='', external_idstring=None, changeids=[], builderNames=None, properties=None)

        :param boolean waited_for: if true, this buildset is being waited for (and thus should continue during a clean shutdown)
        :param string reason: reason for the build set
        :param string external_idstring: external identifier for the buildset
        :param list changeids: changes from which to construct the buildset
        :param list builderNames: a list of builders for the buildset, or None to use the scheduler's configured ``builderNames``
        :param dict properties: properties - in addition to those in the scheduler configuration - to include in the buildset
        :type properties: :py:class:`~buildbot.process.properties.Properties` instance
        :returns: (buildset ID, buildrequest IDs) via Deferred, as for :py:meth:`addBuildsetForSourceStamps`

        Add a buildset for the given changes (``changeids``).
        This will take sourcestamps from the latest of any changes with the same codebase, and will fill in sourcestamps for any codebases for which no changes are included.

    The active state of the scheduler is tracked by the following attribute and methods.

    .. py:attribute:: active

        True if this scheduler is active

    .. py:method:: activate()

        :returns: Deferred

        Subclasses should override this method to initiate any processing that occurs only on active schedulers.
        This is the method from which to call ``startConsumingChanges``, or to set up any timers or message subscriptions.

    .. py:method:: deactivate()

        :returns: Deferred

        Subclasses should override this method to stop any ongoing processing, or wait for it to complete.
        The method's returned Deferred should not fire until the processing is complete.

    The state-manipulation methods are provided by :py:class:`buildbot.util.state.StateMixin`.
    Note that no locking of any sort is performed between these two functions.
    They should *only* be called by an active scheduler.

    .. py:method:: getState(name[, default])

        :param name: state key to fetch
        :param default: default value if the key is not present
        :returns: Deferred

        This calls through to :py:meth:`buildbot.db.state.StateConnectorComponent.getState`, using the scheduler's objectid.

    .. py:method:: setState(name, value)

        :param name: state key
        :param value: value to set for the key
        :returns: Deferred

        This calls through to :py:meth:`buildbot.db.state.StateConnectorComponent.setState`, using the scheduler's objectid.
