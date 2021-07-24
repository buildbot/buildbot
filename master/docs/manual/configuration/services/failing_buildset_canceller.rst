.. _FailingBuildsetCanceller:

FailingBuildsetCanceller
++++++++++++++++++++++++

.. py:class:: buildbot.plugins.util.FailingBuildsetCanceller

The purpose of this service is to cancel builds once one build on a buildset fails.

This is useful for reducing use of resources in cases when there is no need to gather information from all builds of a buildset once one of them fails.

The service may be configured to be track a subset of builds.
This is controlled by the ``filters`` parameter.
The decision on whether to cancel a build is done once a build fails.

The following parameters are supported by the :py:class:`FailingBuildsetCanceller`:

``name``
    (required, a string)
    The name of the service.
    All services must have different names in Buildbot.
    For most use cases value like ``buildset_canceller`` will work fine.

``filters``
    (required, a list of three-element tuples)
    The source stamp filters that specify which builds the build canceller should track.
    The first element of each tuple must be a list of builder names that the filter would apply to.
    The second element of each tuple must be a list of builder names that will have the builders cancelled once a build fails.
    Alternatively, the value ``None`` as the second element of the tuple specifies that all builds should be cancelled.
    The third element of each tuple must be an instance of :py:class:`buildbot.util.SourceStampFilter`.
