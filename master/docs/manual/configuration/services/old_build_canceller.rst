.. _OldBuildCanceller:

OldBuildCanceller
+++++++++++++++++

.. py:class:: buildbot.plugins.util.OldBuildCanceller

The purpose of this service is to cancel builds on branches as soon as a new commit is detected on the branch.

This allows to reduce resource usage in projects that use Buildbot to run tests on pull request branches.
For example, if a developer pushes new commits to the branch, notices and fixes a problem quickly and then pushes again, the builds that have been started on the older commit will be cancelled immediately instead of waiting for builds to finish.

The service may be configured to be track a subset of builds.
This is controlled by the ``filters`` parameter.
The decision on whether to track a build is done on build startup.
Configuration changes are ignored for builds that have already started.

The following parameters are supported by the :py:class:`OldBuildCanceller`:

``name``
    (required, a string)
    The name of the service.
    All services must have different names in Buildbot.
    For most use cases value like ``build_canceller`` will work fine.

``filters``
    (required, a list of two-element tuples)
    The source stamp filters that specify which builds the build canceller should track.
    The first element of each tuple must be a list of builder names that the filter would apply to.
    The second element of each tuple must be an instance of :py:class:`buildbot.util.SourceStampFilter`.
