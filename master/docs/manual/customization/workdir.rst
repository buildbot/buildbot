.. _Factory-Workdir-Functions:

Factory Workdir Functions
-------------------------

It is sometimes helpful to have a build's workdir determined at runtime based on the parameters of
the build. To accomplish this, set the ``workdir`` attribute of the build factory to a
:index:`renderable <renderable>`.

There is deprecated support for setting ``workdir`` to a callable. That callable will be invoked
with the list of :class:`SourceStamp` for the build, and should return the appropriate workdir.
Note that the value must be returned immediately - Deferreds are not supported.

This can be useful, for example, in scenarios with multiple repositories submitting changes to
Buildbot. In this case you likely will want to have a dedicated workdir per repository, since
otherwise a sourcing step with mode = "update" will fail as a workdir with a working copy of
repository A can't be "updated" for changes from a repository B. Here is an example how you can
achieve workdir-per-repo:

.. code-block:: python

        def workdir(source_stamps):
            return hashlib.md5(source_stamps[0].repository).hexdigest()[:8]

        build_factory = factory.BuildFactory()
        build_factory.workdir = workdir

        build_factory.addStep(Git(mode="update"))
        # ...
        builders.append ({'name': 'mybuilder',
                          'workername': 'myworker',
                          'builddir': 'mybuilder',
                          'factory': build_factory})

The end result is a set of workdirs like

.. code-block:: none

    Repo1 => <worker-base>/mybuilder/a78890ba
    Repo2 => <worker-base>/mybuilder/0823ba88

You could make the :func:`workdir()` function compute other paths, based on parts of the repo URL
in the sourcestamp, or lookup in a lookup table based on repo URL. As long as there is a permanent
1:1 mapping between repos and workdir, this will work.
