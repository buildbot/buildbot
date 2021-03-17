.. _Multiple-Codebase-Builds:

Multiple-Codebase Builds
------------------------

What if an end-product is composed of code from several codebases?
Changes may arrive from different repositories within the tree-stable-timer period.
Buildbot will not only use the source-trees that contain changes but also needs the remaining source-trees to build the complete product.

For this reason, a :ref:`Scheduler<Concepts-Scheduler>` can be configured to base a build on a set of several source-trees that can (partly) be overridden by the information from incoming :class:`Change`\s.

As described in :ref:`Source-Stamps <Source-Stamps>`, the source for each codebase is identified by a source stamp, containing its repository, branch and revision.
A full build set will specify a source stamp set describing the source to use for each codebase.

Configuring all of this takes a coordinated approach.  A complete multiple repository configuration consists of:

a *codebase generator*

    Every relevant change arriving from a VC must contain a codebase.
    This is done by a :bb:cfg:`codebaseGenerator` that is defined in the configuration.
    Most generators examine the repository of a change to determine its codebase, using project-specific rules.

some *schedulers*

    Each :bb:cfg:`scheduler<schedulers>` has to be configured with a set of all required ``codebases`` to build a product.
    These codebases indicate the set of required source-trees.
    In order for the scheduler to be able to produce a complete set for each build, the configuration can give a default repository, branch, and revision for each codebase.
    When a scheduler must generate a source stamp for a codebase that has received no changes, it applies these default values.

multiple *source steps* - one for each codebase

    A :ref:`Builder<Concepts-Builder>`'s build factory must include a :ref:`source step<Build-Steps>` for each codebase.
    Each of the source steps has a ``codebase`` attribute which is used to select an appropriate source stamp from the source stamp set for a build.
    This information comes from the arrived changes or from the scheduler's configured default values.

    .. note::

        Each :ref:`source step<Build-Steps>` has to have its own ``workdir`` set in order for the checkout to be done for each codebase in its own directory.

    .. note::

        Ensure you specify the codebase within your source step's Interpolate() calls (e.g. ``http://.../svn/%(src:codebase:branch)s``).
        See :ref:`Interpolate` for details.

.. warning::

    Defining a :bb:cfg:`codebaseGenerator` that returns non-empty (not ``''``) codebases will change the behavior of all the schedulers.
