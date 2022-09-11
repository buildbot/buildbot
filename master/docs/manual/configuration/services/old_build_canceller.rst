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

Certain version control systems have multiple branch names that map to a single logical branch which makes ``OldBuildCanceller`` unable to cancel builds even in the presence of new commits.
The handling of such scenarios is controlled by ``branch_key``.

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

``branch_key``
    (optional, a function that receives source stamp or change dictionary and returns a string)
    Allows customizing the branch that is used to track builds and decide whether to cancel them.
    The function receives a dictionary with at least the following keys: ``project``, ``codebase``, ``repository``, ``branch`` and must return a string.

    The default implementation implements custom handling for the following Version control systems:
     - Gerrit: branches that identify changes (use format ``refs/changes/*/*/*``) have the change iteration number removed.

    Pass ``lambda ss: ss['branch']`` to always use branch property directly.

    Note that ``OldBuildCanceller`` will only cancel builds with the same ``project``, ``codebase``, ``repository`` tuple as incoming change, so these do not need to be taken into account by this function.

