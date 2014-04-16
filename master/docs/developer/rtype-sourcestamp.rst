Source Stamps
=============

.. bb:rtype:: sourcestamp

    :attr integer ssid: the ID of this sourcestamp
    :attr string branch: code branch, or none for the "default branch", whatever that might mean
    :attr string revision: revision for this sourcestamp, or none if unknown
    :attr string project: user-defined project to which this sourcestamp corresponds
    :attr string repository: repository where this sourcestamp occurred
    :attr string codebase: codebase in this repository
    :attr integer created_at: the timestamp when this sourcestamp was created
    :attr patch patch: the patch for this sourcestamp, or none

    A source stamp represents a particular version of the source code.
    Absolute sourcestamps specify this completely, while relative sourcestamps (with revision = None) specify the latest source at the current time.
    Source stamps can also have patches; such stamps describe the underlying revision with the given patch applied.

    Note that, depending on the underlying version-control system, the same revision may describe different code in different branches (e.g., SVN) or may be independent of the branch (e.g., Git).

    The ``created_at`` timestamp can be used to indicate the first time a sourcestamp was seen by Buildbot.
    This provides a reasonable default ordering for sourcestamps when more reliable information is not available.

    .. bb:rpath:: /sourcestamp

        This path selects all sourcestamps.

    .. bb:rpath:: /sourcestamp/:ssid

        :pathkey integer ssid: the ID of the sourcestamp

        This path selects a specific sourcestamp, identified by ID.

