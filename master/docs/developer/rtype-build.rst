Builds
======

.. bb:rtype:: build

    :attr integer buildid: the unique ID of this build
    :attr integer number: the number of this build (sequential for a given builder)
    :attr integer builderid: id of the builder for this build
    :attr Link builder_link: link to the builder for this build
    :attr integer buildrequestid: build request for which this build was performed, or None if no such request exists
    :attr Link buildrequest_link: link to the indicated build request
    :attr integer slaveid: the slave this build ran on
    :attr Link slave_link: link to the slave that this build ran on
    :attr integer masterid: the master this build ran on
    :attr Link master_link: link to the master that this build ran on
    :attr timestamp started_at: time at which this build started
    :attr boolean complete: true if this build is complete
    :attr timestamp complete_at: time at which this build was complete, or None if it's still running
    :attr integer results: the results of the build (see :ref:`Build-Result-Codes`), or None if not complete
    :attr list state_strings: a list of strings giving progressively more detail on the state of the build.
        The first is usually one word or phrase; the remainder are sized for one-line display.
    :attr Link link: link for this build

    .. todo:

        * Currently build properties aren't available in this resource type

    .. note:

        Build requests are not available in pickled builds, so ``brid`` is always None for build requests imported from older versions of Buildbot.
        The field will always be set for new builds.

    This resource type describes completed and in-progress builds.
    Much of the contextual data for a build is associated with the build request, and through it the buildset.

    .. bb:event:: build.$builderid.$buildid.new

        The build has just started.
        Builds are started when they are created, so this also indicates the creation of a new build.

    .. bb:event:: build.$builderid.$buildid.complete

        The build has just been completed.

    .. bb:event:: build.$builderid.$buildid.newstate

        The build's state (``state_strings``) has changed.

    .. bb:rpath:: /build

        This path lists builds, sorted by ID.

    .. bb:rpath:: /build/:buildid

        :pathkey integer buildid: the ID of the build

        This path selects a specific build, identified by ID.

    .. bb:rpath:: /builder/:builderid/build

        :pathkey integer builderid: the ID of the builder

        This path lists builds performed for the identified builder, sorted by number.

    .. bb:rpath:: /builder/:builderid/build/:number

        :pathkey integer builderid: the ID of the builder
        :pathkey integer number: the build number within that builder

        This path selects a specific build, identified by its builder and the number within that builder.

    .. bb:rpath:: /buildrequest/:buildrequestid/build

        :pathkey integer buildrequestid: the ID of the build request

        This path selects builds for a given buildrequest.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.builds.BuildResourceType

    .. py:method:: newBuild(builderid, buildrequestid, buildslaveid)

        :param integer builderid: builder performing this build
        :param integer buildrequstid: build request being built
        :param integer slaveid: slave on which this build is performed
        :returns: (buildid, number) via Deferred

        Create a new build resource and return its ID.
        The state strings for the new build will be set to 'starting'.

    .. py:method:: setBuildStateStrings(buildid, state_strings)

        :param integer buildid: the build to modify
        :param list state_strings: new state strings for this build

        Replace the existing state strings for a build with a new list.

    .. py:method:: finishBuild(buildid, results)

        :param integer buildid: the build to modify
        :param integer results: the build's results

        Mark the build as finished at the current time, with the given results.
