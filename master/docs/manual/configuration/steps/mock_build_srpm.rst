.. bb:step:: MockBuildSRPM

.. _Step-MockBuildSRPM:

MockBuildSRPM Step
++++++++++++++++++

The :bb:step:`MockBuildSRPM` step builds a SourceRPM based on a spec file and optionally a source directory:

Mock (http://fedoraproject.org/wiki/Projects/Mock) creates chroots and builds packages in them.
It populates the changeroot with a basic system and the packages listed as build requirement.
The type of chroot to build is specified with the ``root`` parameter.
To use mock your Buildbot user must be added to the ``mock`` group.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.MockBuildSRPM(root='default', spec='mypkg.spec'))

The step takes the following parameters

``root``
    Use chroot configuration defined in ``/etc/mock/<root>.cfg``.

``resultdir``
    The directory where the logfiles and the SourceRPM are written to.

``spec``
    Build the SourceRPM from this spec file.

``sources``
    Path to the directory containing the sources, defaulting to ``.``.

.. note::

   It is necessary to pass the ``resultdir`` parameter to let the master
   watch for (and display) changes to :file:`build.log`,
   :file:`root.log`, and :file:`state.log`.
