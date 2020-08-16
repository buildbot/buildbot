.. bb:step:: MockRebuild

.. _Step-MockRebuild:

MockRebuild
+++++++++++

The :bb:step:`MockRebuild` step rebuilds a SourceRPM package:

Mock (http://fedoraproject.org/wiki/Projects/Mock) creates chroots and builds packages in them.
It populates the changeroot with a basic system and the packages listed as build requirement.
The type of chroot to build is specified with the ``root`` parameter.
To use mock your Buildbot user must be added to the ``mock`` group.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.MockRebuild(root='default', srpm='mypkg-1.0-1.src.rpm'))

The step takes the following parameters

``root``
    Uses chroot configuration defined in ``/etc/mock/<root>.cfg``.

``resultdir``
    The directory where the logfiles and the SourceRPM are written to.

``srpm``
    The path to the SourceRPM to rebuild.

.. note::

   It is necessary to pass the ``resultdir`` parameter to let the master
   watch for (and display) changes to :file:`build.log`,
   :file:`root.log`, and :file:`state.log`.
