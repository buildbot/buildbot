.. -*- rst -*-

.. bb:cfg:: builders

.. _Builder-Configuration:

Builder Configuration
---------------------

.. contents::
    :depth: 1
    :local:

The :bb:cfg:`builders` configuration key is a list of objects giving configuration for the Builders.
For more information on the function of Builders in Buildbot, see :ref:`the Concepts chapter <Builder>`.
The class definition for the builder configuration is in :file:`buildbot.config`.
However there is a much simpler way to use it, so in the configuration file, its use looks like::

    from buildbot.plugins import util
    c['builders'] = [
        util.BuilderConfig(name='quick', workernames=['bot1', 'bot2'], factory=f_quick),
        util.BuilderConfig(name='thorough', workername='bot1', factory=f_thorough),
    ]

``BuilderConfig`` takes the following keyword arguments:

``name``
    This specifies the Builder's name, which is used in status reports.

``workername``

``workernames``
    These arguments specify the worker or workers that will be used by this Builder.
    All workers names must appear in the :bb:cfg:`workers` configuration parameter.
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
    This is where checkouts, compiles, and tests are run.
    If not set, defaults to ``builddir``.
    If a worker is connected to multiple builders that share the same ``workerbuilddir``, make sure the worker is set to run one build at a time or ensure this is fine to run multiple builds from the same directory simultaneously.

``tags``
    If provided, this is a list of strings that identifies tags for the builder.
    Status clients can limit themselves to a subset of the available tags.
    A common use for this is to add new builders to your setup (for a new module, or for a new worker) that do not work correctly yet and allow you to integrate them with the active builders.
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

``locks``
    This argument specifies a list of locks that apply to this builder; see :ref:`Interlocks`.

``env``
    A Builder may be given a dictionary of environment variables in this parameter.
    The variables are used in :bb:step:`ShellCommand` steps in builds created by this builder.
    The environment variables will override anything in the worker's environment.
    Variables passed directly to a :class:`ShellCommand` will override variables of the same name passed to the Builder.

    For example, if you have a pool of identical workers it is often easier to manage variables like :envvar:`PATH` from Buildbot rather than manually editing it inside of the workers' environment.

    ::

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

``description``
    A builder may be given an arbitrary description, which will show up in the web status on the builder's page.

.. index:: Builds; merging

.. _Collapsing-Build-Requests:

Collapsing Build Requests
~~~~~~~~~~~~~~~~~~~~~~~~~

When more than one build request is available for a builder, Buildbot can "collapse" the requests into a single build.
This is desirable when build requests arrive more quickly than the available workers can satisfy them, but has the drawback that separate results for each build are not available.

Requests are only candidated for a merge if both requests have exactly the same :ref:`codebases<Attr-Codebase>`.

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
* Either both source stamps are associated with changes, or neither are associated with changes but they have matching revisions.

.. index:: Builds; priority

.. _Prioritizing-Builds:

Prioritizing Builds
~~~~~~~~~~~~~~~~~~~

The :class:`BuilderConfig` parameter ``nextBuild`` can be use to prioritize build requests within a builder.
Note that this is orthogonal to :ref:`Prioritizing-Builders`, which controls the order in which builders are called on to start their builds.
The details of writing such a function are in :ref:`Build-Priority-Functions`.

Such a function can be provided to the BuilderConfig as follows::

    def pickNextBuild(builder, requests):
        ...
    c['builders'] = [
        BuilderConfig(name='test', factory=f,
            nextBuild=pickNextBuild,
            workernames=['worker1', 'worker2', 'worker3', 'worker4']),
    ]
