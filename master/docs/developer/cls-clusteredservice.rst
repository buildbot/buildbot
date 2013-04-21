.. index:: Service utilities; ClusteredService

ClusteredService
================

Some services in buildbot must have only one "active" instance at any given time. In a single-master configuration,
this requirement is trivial to maintain. In a multiple-master configuration, some arbitration is required to ensure
that the service is always active on exactly one master in the cluster.

For example, a particular daily scheduler could be configured on multiple masters, but only one of them should
actually trigger the required builds.

.. class:: buildbot.util.service.ClusteredService

    A base class for a service that must have only one "active" instance in a buildbot configuration.

    Each instance of the service is started and stopped via the usual twisted ``startService`` and ``stopService``
    methods. This utility class hooks into those methods in order to run an arbitration strategy to pick the
    one instance that should actually be "active".

    The arbitration strategy is implemented via a polling loop. When each service instance starts, it
    immediately offers to take over as the active instance (via ``_claimService``).

    If successful, the ``activate`` method is called. Once active, the instance remains active until it is explicitly stopped (eg, via ``stopService``) or otherwise fails. When this happens, the ``deactivate`` method is invoked
    and the "active" status is given back to the cluster (via ``_unclaimService``).

    If another instance is already active, this offer fails, and the instance will poll periodically
    to try again. The polling strategy helps guard against active instances that might silently disappear and
    leave the service without any active instance running.

    Subclasses should use these methods to hook into this activation scheme:

    .. method:: activate()

        When a particular instance of the service is chosen to be the one "active" instance, this method
        is invoked. It is the corollary to twisted's ``startService``.

    .. method:: deactivate()

        When the one "active" instance must be deactivated, this method is invoked. It is the corollary to
        twisted's ``stopService``.

    .. method:: isActive()

        Returns whether this particular instance is the active one.

    The arbitration strategy is implemented via the following required methods:

    .. method:: _getServiceId()

        The "service id" uniquely represents this service in the cluster. Each instance of this service must
        have this same id, which will be used in the arbitration to identify candidates for activation. This
        method may return a Deferred.

    .. method:: _claimService()

        An instance is attempting to become the one active instance in the cluster. This method must
        return `True` or `False` (optionally via a Deferred) to represent whether this instance's offer
        to be the active one was accepted. If this returns `True`, the ``activate`` method will be called
        for this instance.

    .. method:: _unclaimService()

        Surrender the "active" status back to the cluster and make it available for another instance.
        This will only be called on an instance that successfully claimed the service and has been activated
        and after its ``deactivate`` has been called. Therefore, in this method it is safe to reassign
        the "active" status to another instance. This method may return a Deferred.
