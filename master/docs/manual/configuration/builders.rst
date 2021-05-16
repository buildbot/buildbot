.. -*- rst -*-

.. bb:cfg:: builders

.. _Builder-Configuration:

Builder Configuration
---------------------

.. contents::
    :depth: 1
    :local:

The :bb:cfg:`builders` configuration key is a list of objects holding the configuration of the Builders.
For more information on the Builders' function in Buildbot, see :ref:`the Concepts chapter <Concepts-Builder>`.
The class definition for the builder configuration is in :file:`buildbot.config`.
However, there is a simpler way to use it and it looks like this:

.. code-block:: python

    from buildbot.plugins import util
    c['builders'] = [
        util.BuilderConfig(name='quick', workernames=['bot1', 'bot2'], factory=f_quick),
        util.BuilderConfig(name='thorough', workername='bot1', factory=f_thorough),
    ]

``BuilderConfig`` takes the following keyword arguments:

``name``
    The name of the Builder, which is used in status reports.

``workername`` ``workernames``
    These arguments specify the worker or workers that will be used by this Builder.
    All worker names must appear in the :bb:cfg:`workers` configuration parameter.
    Each worker can accommodate multiple builders.
    The ``workernames`` parameter can be a list of names, while ``workername`` can specify only one worker.

``factory``
    This is a :class:`buildbot.process.factory.BuildFactory` instance which controls how the build is performed by defining the steps in the build.
    Full details appear in their own section, :ref:`Build-Factories`.

Other optional keys may be set on each ``BuilderConfig``:

``builddir``
    Specifies the name of a subdirectory of the master's basedir in which everything related to this builder will be stored.
    This holds build status information.
    If not set, this parameter defaults to the builder name, with some characters escaped.
    Each builder must have a unique build directory.

``workerbuilddir``
    Specifies the name of a subdirectory (under the worker's configured base directory) in which everything related to this builder will be placed on the worker.
    This is where checkouts, compilations, and tests are run.
    If not set, defaults to ``builddir``.
    If a worker is connected to multiple builders that share the same ``workerbuilddir``, make sure the worker is set to run one build at a time or ensure this is fine to run multiple builds from the same directory simultaneously.

``tags``
    If provided, this is a list of strings that identifies tags for the builder.
    Status clients can limit themselves to a subset of the available tags.
    A common use for this is to add new builders to your setup (for a new module or a new worker) that do not work correctly yet and allow you to integrate them with the active builders.
    You can tag these new builders with a ``test`` tag, make your main status clients ignore them, and have only private status clients pick them up.
    As soon as they work, you can move them over to the active tag.

``nextWorker``
     If provided, this is a function that controls which worker will be assigned future jobs.
     The function is passed three arguments, the :class:`Builder` object which is assigning a new job, a list of :class:`WorkerForBuilder` objects and the :class:`BuildRequest`.
     The function should return one of the :class:`WorkerForBuilder` objects, or ``None`` if none of the available workers should be used.
     As an example, for each ``worker`` in the list, ``worker.worker`` will be a :class:`Worker` object, and ``worker.worker.workername`` is the worker's name.
     The function can optionally return a Deferred, which should fire with the same results.

``nextBuild``
    If provided, this is a function that controls which build request will be handled next.
    The function is passed two arguments, the :class:`Builder` object which is assigning a new job, and a list of :class:`BuildRequest` objects of pending builds.
    The function should return one of the :class:`BuildRequest` objects, or ``None`` if none of the pending builds should be started.
    This function can optionally return a Deferred which should fire with the same results.

``canStartBuild``
    If provided, this is a function that can veto whether a particular worker should be used for a given build request.
    The function is passed three arguments: the :class:`Builder`, a :class:`Worker`, and a :class:`BuildRequest`.
    The function should return ``True`` if the combination is acceptable, or ``False`` otherwise.
    This function can optionally return a Deferred which should fire with the same results.

    See :ref:`canStartBuild-Functions` for a concrete example.

``locks``
    A list of ``Locks`` (instances of :class:`buildbot.locks.WorkerLock` or :class:`buildbot.locks.MasterLock`) that should be acquired before starting a :class:`Build` from this :class:`Builder`.
    Alternatively, this could be a renderable that returns this list depending on properties related to the build that is just about to be created.
    This lets you defer picking the locks to acquire until it is known which :class:`Worker` a build would get assigned to.
    The properties available to the renderable include all properties that are set to the build before its first step excluding the properties that come from the build itself and the ``builddir`` property that comes from worker.
    The ``Locks`` will be released when the build is complete.
    Note that this is a list of actual :class:`Lock` instances, not names.
    Also note that all Locks must have unique names.
    See :ref:`Interlocks`.

``env``
    A Builder may be given a dictionary of environment variables in this parameter.
    The variables are used in :bb:step:`ShellCommand` steps in builds created by this builder.
    The environment variables will override anything in the worker's environment.
    Variables passed directly to a :class:`ShellCommand` will override variables of the same name passed to the Builder.

    For example, if you have a pool of identical workers it is often easier to manage variables like :envvar:`PATH` from Buildbot rather than manually editing them in the workers' environment.

    .. code-block:: python

        f = factory.BuildFactory
        f.addStep(ShellCommand(
                      command=['bash', './configure']))
        f.addStep(Compile())

        c['builders'] = [
          BuilderConfig(name='test', factory=f,
                workernames=['worker1', 'worker2', 'worker3', 'worker4'],
                env={'PATH': '/opt/local/bin:/opt/app/bin:/usr/local/bin:/usr/bin'}),
        ]

    Unlike most builder configuration arguments, this argument can contain renderables.

.. index:: Builds; merging

``collapseRequests``
    Specifies how build requests for this builder should be collapsed.
    See :ref:`Collapsing-Build-Requests`, below.

.. index:: Properties; builder

``properties``
    A builder may be given a dictionary of :ref:`Build-Properties` specific for this builder in this parameter.
    Those values can be used later on like other properties.
    :ref:`Interpolate`.

``defaultProperties``
    Similar to the ``properties`` parameter.
    But ``defaultProperties`` will only be added to :ref:`Build-Properties` if they are not already set by :ref:`another source <Properties>`.

``description``
    A builder may be given an arbitrary description, which will show up in the web status on the builder's page.

.. index:: Builds; merging

.. _Collapsing-Build-Requests:

Collapsing Build Requests
~~~~~~~~~~~~~~~~~~~~~~~~~

When more than one build request is available for a builder, Buildbot can "collapse" the requests into a single build.
This is desirable when build requests arrive more quickly than the available workers can satisfy them, but has the drawback that separate results for each build are not available.

Requests are only candidated for a merge if both requests have exactly the same :ref:`codebases<Change-Attr-Codebase>`.

This behavior can be controlled globally, using the :bb:cfg:`collapseRequests` parameter, and on a per-:class:`Builder` basis, using the ``collapseRequests`` argument to the :class:`Builder` configuration.
If ``collapseRequests`` is given, it completely overrides the global configuration.

Possible values for both ``collapseRequests`` configurations are:

``True``
    Requests will be collapsed if their sourcestamp are compatible (see below for definition of compatible).

``False``
    Requests will never be collapsed.

``callable(builder, req1, req2)``
    Requests will be collapsed if the callable returns true.
    See :ref:`Collapse-Request-Functions` for detailed example.

Sourcestamps are compatible if all of the below conditions are met:

* Their codebase, branch, project, and repository attributes match exactly
* Neither source stamp has a patch (e.g., from a try scheduler)
* Either both source stamps are associated with changes, or neither is associated with changes but they have matching revisions.

.. index:: Builds; priority

.. _Prioritizing-Builds:

Prioritizing Builds
~~~~~~~~~~~~~~~~~~~

The :class:`BuilderConfig` parameter ``nextBuild`` can be used to prioritize build requests within a builder.
Note that this is orthogonal to :ref:`Prioritizing-Builders`, which controls the order in which builders are called on to start their builds.
The details of writing such a function are in :ref:`Build-Priority-Functions`.

Such a function can be provided to the BuilderConfig as follows:

.. code-block:: python

    def pickNextBuild(builder, requests):
        ...
    c['builders'] = [
        BuilderConfig(name='test', factory=f,
            nextBuild=pickNextBuild,
            workernames=['worker1', 'worker2', 'worker3', 'worker4']),
    ]

.. _Virtual-Builders:

Virtual Builders
~~~~~~~~~~~~~~~~

:ref:`Dynamic-Trigger` is a method which allows to trigger the same builder, with different parameters.
This method is used by frameworks which store the build config along side the source code like Buildbot_travis_.
The drawback of this method is that it is difficult to extract statistics for similar builds.
The standard dashboards are not working well due to the fact that all the builds are on the same builder.

In order to overcome these drawbacks, Buildbot has the concept of virtual builder.
If a build has the property ``virtual_builder_name``, it will automatically attach to that builder instead of the original builder.
That created virtual builder is not attached to any master and is only used for better sorting in the UI and better statistics.
The original builder and worker configuration is still used for all other build behaviors.

The virtual builder metadata is configured with the following properties:

* ``virtual_builder_name``: The name of the virtual builder.

* ``virtual_builder_description``: The description of the virtual builder.

* ``virtual_builder_tags``: The tags for the virtual builder.

You can also use virtual builders with :bb:sched:`SingleBranchScheduler`.
For example if you want to automatically build all branches in your project without having to manually create a new builder each time one is added:

.. code-block:: python

    c['schedulers'].append(schedulers.SingleBranchScheduler(
        name='myproject-epics',
        change_filter=util.ChangeFilter(branch_re='epics/.*'),
        builderNames=['myproject-epics'],
        properties={
            'virtual_builder_name': util.Interpolate("myproject-%(ss::branch)s")
        }
    ))

.. _Buildbot_travis: https://github.com/buildbot/buildbot_travis
