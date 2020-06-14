.. bb:step:: RpmBuild

.. _Step-RpmBuild:

RpmBuild
++++++++

The :bb:step:`RpmBuild` step builds RPMs based on a spec file:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.RpmBuild(specfile="proj.spec", dist='.el5'))

The step takes the following parameters

``specfile``
    The ``.spec`` file to build from

``topdir``
    Definition for ``_topdir``, defaulting to the workdir.

``builddir``
    Definition for ``_builddir``, defaulting to the workdir.

``rpmdir``
    Definition for ``_rpmdir``, defaulting to the workdir.

``sourcedir``
    Definition for ``_sourcedir``, defaulting to the workdir.

``srcrpmdir``
    Definition for ``_srcrpmdir``, defaulting to the workdir.

``dist``
    Distribution to build, used as the definition for ``_dist``.

``define``
    A dictionary of additional definitions to declare.

``autoRelease``
    If true, use the auto-release mechanics.

``vcsRevision``
    If true, use the version-control revision mechanics.
    This uses the ``got_revision`` property to determine the revision and define ``_revision``.
    Note that this will not work with multi-codebase builds.
