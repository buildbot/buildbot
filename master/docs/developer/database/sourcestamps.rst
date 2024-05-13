Source stamps connector
~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.sourcestamps

.. index:: double: SourceStamps; DB Connector Component

.. py:class:: SourceStampsConnectorComponent

    This class manages source stamps, as stored in the database.
    A source stamp uniquely identifies a particular version of a single codebase.
    Source stamps are identified by their ID.
    It is safe to use sourcestamp ID equality as a proxy for source stamp equality.
    For example, all builds of a particular version of a codebase will share the same sourcestamp ID.
    This equality does not extend to patches: two sourcestamps generated with exactly the same patch will have different IDs.

    Relative source stamps have a ``revision`` of None, meaning "whatever the latest is when this sourcestamp is interpreted".
    While such source stamps may correspond to a wide array of revisions over the lifetime of a Buildbot installation, they will only ever have one ID.

    An instance of this class is available at ``master.db.sourcestamps``.

    Sourcestamps are represented by a :class:`SourceStampModel` dataclass with the following fields:

    .. index:: ssid, ssdict

    * ``ssid``
    * ``branch`` (branch, or ``None`` for default branch)
    * ``revision`` (revision, or ``None`` to indicate the latest revision, in
        which case this is a relative source stamp)
    * ``repository`` (repository containing the source; never ``None``)
    * ``created_at`` (timestamp when this stamp was first created)
    * ``codebase`` (codebase this stamp is in; never ``None``)
    * ``project`` (project this source is for; never ``None``)
    * ``patch`` (a ``PatchModel`` or ``None``, see below)

    .. index:: patch

    :class:`PatchModel`

    * ``patchid`` (ID of the patch)
    * ``body`` (body of the patch, or ``None``)
    * ``level`` (directory stripping level of the patch, or ``None``)
    * ``subdir`` (subdirectory in which to apply the patch, or ``None``)
    * ``author`` (author of the patch, or ``None``)
    * ``comment`` (comment for the patch, or ``None``)

    Note that the patch body is a bytestring, not a unicode string.

    .. py:method:: findSourceStampId(branch=None, revision=Node, repository=None, project=None, patch_body=None, patch_level=None, patch_author=None, patch_comment=None, patch_subdir=None)

        :param branch:
        :type branch: unicode string or None
        :param revision:
        :type revision: unicode string or None
        :param repository:
        :type repository: unicode string or None
        :param project:
        :type project: unicode string or None
        :param codebase:
        :type codebase: unicode string (required)
        :param patch_body: patch body
        :type patch_body: bytes or unicode string or None
        :param patch_level: patch level
        :type patch_level: integer or None
        :param patch_author: patch author
        :type patch_author: unicode string or None
        :param patch_comment: patch comment
        :type patch_comment: unicode string or None
        :param patch_subdir: patch subdir
        :type patch_subdir: unicode string or None
        :returns: ssid, via Deferred

        Create a new SourceStamp instance with the given attributes, or find an existing one.
        In either case, return its ssid.
        The arguments all have the same meaning as in an :class:`SourceStampModel`.

        If a new SourceStamp is created, its ``created_at`` is set to the current time.

    .. py:method:: getSourceStamp(ssid)

        :param ssid: sourcestamp to get
        :param no_cache: bypass cache and always fetch from database
        :type no_cache: boolean
        :returns: :class:`SourceStampModel`, or ``None``, via Deferred

        Get an :class:`SourceStampModel` representing the given source stamp, or ``None`` if no
        such source stamp exists.

    .. py:method:: getSourceStamps()

        :returns: list of :class:`SourceStampModel`, via Deferred

        Get all sourcestamps in the database.
        You probably don't want to do this!
        This method will be extended to allow appropriate filtering.

    .. py:method:: get_sourcestamps_for_buildset(buildsetid)

        :param buildsetid: buildset ID
        :returns: list of :class:`SourceStampModel`, via Deferred

        Get sourcestamps related to a buildset.

    .. py:method:: getSourceStampsForBuild(buildid)

        :param buildid: build ID
        :returns: list of :class:`SourceStampModel`, via Deferred

        Get sourcestamps related to a build.
