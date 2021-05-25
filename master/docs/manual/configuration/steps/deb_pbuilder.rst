.. bb:step:: DebPbuilder

.. _Step-DebPbuilder:

DebPbuilder
+++++++++++

The :bb:step:`DebPbuilder` step builds Debian packages within a chroot built by :command:`pbuilder`.
It populates the chroot with a basic system and the packages listed as build requirements.
The type of the chroot to build is specified with the ``distribution``, ``distribution`` and ``mirror`` parameter.
To use pbuilder, your Buildbot user must have the right to run :command:`pbuilder` as root using :command:`sudo`.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.DebPbuilder())

The step takes the following parameters

``architecture``
    Architecture to build chroot for.

``distribution``
    Name, or nickname, of the distribution.
    Defaults to 'stable'.

``basetgz``
    Path of the basetgz to use for building.

``mirror``
    URL of the mirror used to download the packages from.

``othermirror``
    List of additional ``deb URL ...`` lines to add to ``sources.list``.

``extrapackages``
    List if packages to install in addition to the base system.

``keyring``
    Path to a gpg keyring to verify the downloaded packages.
    This is necessary if you build for a foreign distribution.

``components``
    Repos to activate for chroot building.

.. bb:step:: DebCowbuilder

DebCowbuilder
+++++++++++++

The :bb:step:`DebCowbuilder` step is a subclass of :bb:step:`DebPbuilder`, which use cowbuilder instead of pbuilder.
