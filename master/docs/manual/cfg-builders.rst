.. -*- rst -*-

.. bb:cfg:: builders

.. _Builder-Configuration:

Builder Configuration
---------------------

The :bb:cfg:`builders` configuration key is a list of objects giving
configuration for the Builders.  For more information, see :ref:`Builder`.  The
class definition for the builder configuration is in :file:`buildbot.config`.
In the configuration file, its use looks like::

    from buildbot.config import BuilderConfig
    c['builders'] = [
        BuilderConfig(name='quick', slavenames=['bot1', 'bot2'], factory=f_quick),
        BuilderConfig(name='thorough', slavename='bot1', factory=f_thorough),
    ]

The constructor takes the following keyword arguments:

``name``
    This specifies the Builder's name, which is used in status reports.

``slavename``

``slavenames``
    These arguments specify the buildslave or buildslaves that will be used by this
    Builder.  All slaves names must appear in the :bb:cfg:`slaves` list. Each
    buildslave can accomodate multiple :class:`Builder`\s.  The ``slavenames`` parameter
    can be a list of names, while ``slavename`` can specify only one slave.

``factory``
    This is a :class:`buildbot.process.factory.BuildFactory` instance which
    controls how the build is performed. Full details appear in their own
    section, :ref:`Build-Factories`. Parameters like the location of the CVS
    repository and the compile-time options used for the build are
    generally provided as arguments to the factory's constructor.


Other optional keys may be set on each :class:`Builder`:

``builddir``
    Specifies the name of a subdirectory (under the base directory) in which
    everything related to this builder will be placed on the buildmaster.
    This holds build status information. If not set, defaults to ``name``
    with some characters escaped. Each builder must have a unique build
    directory.

``slavebuilddir``
    Specifies the name of a subdirectory (under the base directory) in which
    everything related to this builder will be placed on the buildslave.
    This is where checkouts, compiles, and tests are run. If not set,
    defaults to ``builddir``. If a slave is connected to multiple builders
    that share the same ``slavebuilddir``, make sure the slave is set to
    run one build at a time or ensure this is fine to run multiple builds from
    the same directory simultaneously.

``category``
    If provided, this is a string that identifies a category for the
    builder to be a part of. Status clients can limit themselves to a
    subset of the available categories. A common use for this is to add
    new builders to your setup (for a new module, or for a new buildslave)
    that do not work correctly yet and allow you to integrate them with
    the active builders. You can put these new builders in a test
    category, make your main status clients ignore them, and have only
    private status clients pick them up. As soon as they work, you can
    move them over to the active category.

``nextSlave``
    If provided, this is a function that controls which slave will be assigned
    future jobs. The function is passed two arguments, the :class:`Builder`
    object which is assigning a new job, and a list of :class:`BuildSlave`
    objects. The function should return one of the :class:`BuildSlave`
    objects, or ``None`` if none of the available slaves should be
    used.

``nextBuild``
    If provided, this is a function that controls which build request will be
    handled next. The function is passed two arguments, the :class:`Builder`
    object which is assigning a new job, and a list of :class:`BuildRequest`
    objects of pending builds. The function should return one of the
    :class:`BuildRequest` objects, or ``None`` if none of the pending
    builds should be started. This function can optionally return a
    Deferred which should fire with the same results.

``locks``
    This argument specifies a list of locks that apply to this builder; :ref:`Interlocks`.

``env``
    A Builder may be given a dictionary of environment variables in this parameter.
    The variables are used in :bb:step:`ShellCommand` steps in builds created by this
    builder. The environment variables will override anything in the buildslave's
    environment. Variables passed directly to a :class:`ShellCommand` will override
    variables of the same name passed to the Builder.

    For example, if you have a pool of identical slaves it is often easier to manage
    variables like :envvar:`PATH` from Buildbot rather than manually editing it inside of
    the slaves' environment. ::

        f = factory.BuildFactory
        f.addStep(ShellCommand(
                      command=['bash', './configure']))
        f.addStep(Compile())
        
        c['builders'] = [
          BuilderConfig(name='test', factory=f,
                slavenames=['slave1', 'slave2', 'slave3', 'slave4'],
                env=@{'PATH': '/opt/local/bin:/opt/app/bin:/usr/local/bin:/usr/bin'@}),
        ]

``mergeRequests``
    Specifies how build requests for this builder should be merged> See
    :ref:`Merging-Build-Requests` for details.

``properties``
    A builder may be given a dictionnary of :ref:`Build-Properties`
    specific for this builder in this parameter. Those values can be used
    later on like other properties. :ref:`WithProperties`.

.. index:: Builds; merging

.. _Merging-Build-Requests:

Merging Build Requests
----------------------

When more than one build request is available for a builder, Buildbot can
"merge" the requests into a single build.  This is desirable when build
requests arrive more quickly than the available slaves can satisfy them, but
has the drawback that separate results for each build are not available.

This behavior can be controlled globally, using the :bb:cfg:`mergeRequests`
parameter, and on a per-:class:`Builder` basis, using the ``mergeRequests`` argument
to the :class:`Builder` configuration.  If ``mergeRequests`` is given, it completely
overrides the global configuration.

For either configuration parameter, a value of ``True`` (the default) causes
buildbot to merge BuildRequests that have "compatible" source stamps.  Source
stamps are compatible if:

* their branch, project, and repository attributes match exactly;
* neither source stamp has a patch (e.g., from a try scheduler); and
* either both source stamps are associated with changes, or neither ar
  associated with changes but they have matching revisions.

This algorithm is implemented by the :class:`SourceStamp` method :func:`canBeMergedWith`.

A configuration value of ``False`` indicates that requests should never be
merged.

The configuration value can also be a callable, specifying a custom merging
function.  See :ref:`Merge-Request-Functions` for details.

.. index:: Builds; priority

.. _Prioritizing-Builds:

Prioritizing Builds
-------------------

The :class:`BuilderConfig` parameter ``nextBuild`` can be use to prioritize
build requests within a builder. Note that this is orthogonal to
:ref:`Prioritizing-Builders`, which controls the order in which builders are
called on to start their builds.

.. code-block:: python

   def nextBuild(bldr, requests):
       for r in requests:
           if r.source.branch == 'release':
               return r
       return requests[0]

   c['builders'] = [
     BuilderConfig(name='test', factory=f,
           nextBuild=nextBuild,
           slavenames=['slave1', 'slave2', 'slave3', 'slave4']), 
   ]

