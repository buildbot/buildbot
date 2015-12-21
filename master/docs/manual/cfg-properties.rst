.. index:: Properties

.. _Properties:

Properties
==========

Build properties are a generalized way to provide configuration information to build steps; see :ref:`Build-Properties` for the conceptual overview of properties.

.. contents::
    :depth: 1
    :local:

Some build properties come from external sources and are set before the build begins; others are set during the build, and available for later steps.
The sources for properties are:

:bb:cfg:`global configuration <properties>`
    These properties apply to all builds.
:ref:`schedulers <Configuring-Schedulers>`
    A scheduler can specify properties that become available to all builds it starts.
:ref:`changes <Change-Sources>`
    A change can have properties attached to it, supplying extra information gathered by the change source.
    This is most commonly used with the :bb:cmdline:`sendchange` command.
forced builds
    The "Force Build" form allows users to specify properties
:bb:cfg:`buildslaves <slaves>`
    A buildslave can pass properties on to the builds it performs.
:ref:`builds <Common-Build-Properties>`
    A build automatically sets a number of properties on itself.
:bb:cfg:`builders <builders>`
    A builder can set properties on all the builds it runs.
:ref:`steps <Build-Steps>`
    The steps of a build can set properties that are available to subsequent steps.
    In particular, source steps set the `got_revision` property.

If the same property is supplied in multiple places, the final appearance takes precedence.
For example, a property set in a builder configuration will override one supplied by a scheduler.

Properties are stored internally in JSON format, so they are limited to basic types of data: numbers, strings, lists, and dictionaries.

.. index:: single: Properties; Common Properties

.. _Common-Build-Properties:

Common Build Properties
-----------------------

The following build properties are set when the build is started, and are available to all steps.

.. index:: single: Properties; got_revision

``got_revision``
    This property is set when a :class:`Source` step checks out the source tree, and provides the revision that was actually obtained from the VC system.
    In general this should be the same as ``revision``, except for non-absolute sourcestamps, where ``got_revision`` indicates what revision was current when the checkout was performed.
    This can be used to rebuild the same source code later.

    .. note::

       For some VC systems (Darcs in particular), the revision is a large string containing newlines, and is not suitable for interpolation into a filename.

    For multi-codebase builds (where codebase is not the default `''`), this property is a dictionary, keyed by codebase.

.. index:: single: Properties; buildername

``buildername``
    This is a string that indicates which :class:`Builder` the build was a part of.
    The combination of buildername and buildnumber uniquely identify a build.

.. index:: single: Properties; buildnumber

``buildnumber``
    Each build gets a number, scoped to the :class:`Builder` (so the first build performed on any given :class:`Builder` will have a build number of 0).
    This integer property contains the build's number.

.. index:: single: Properties; slavename

``slavename``
    This is a string which identifies which buildslave the build is running on.

.. index:: single: Properties; scheduler

``scheduler``
    If the build was started from a scheduler, then this property will contain the name of that scheduler.

``workdir``
    The absolute path of the base working directory on the slave, of the current builder.

.. index:: single: Properties; workdir

For single codebase builds, where the codebase is `''`, the following :ref:`Source-Stamp-Attributes` are also available as properties: ``branch``, ``revision``, ``repository``, and ``project`` .

.. _Source-Stamp-Attributes:

Source Stamp Attributes
-----------------------

.. index:: single: Properties; branch

``branch``
``revision``
``repository``
``project``
``codebase``

    For details of these attributes see :doc:`/manual/concepts`.

``changes``

    This attribute is a list of dictionaries representing the changes that make up this sourcestamp.

Using Properties in Steps
-------------------------

For the most part, properties are used to alter the behavior of build steps during a build.
This is done by using :index:`renderables <renderable>` (objects implementing the :class:`~buildbot.interfaces.IRenderable` interface) as step parameters.
When the step is started, each such object is rendered using the current values of the build properties, and the resultant rendering is substituted as the actual value of the step parameter.

Buildbot offers several renderable object types covering common cases.
It's also possible to :ref:`create custom renderables <Custom-Renderables>`.

.. note::

    Properties are defined while a build is in progress; their values are not available when the configuration file is parsed.
    This can sometimes confuse newcomers to Buildbot!
    In particular, the following is a common error::

        if Property('release_train') == 'alpha':
            f.addStep(...)

    This does not work because the value of the property is not available when the ``if`` statement is executed.
    However, Python will not detect this as an error - you will just never see the step added to the factory.

You can use renderables in most step parameters.
Please file bugs for any parameters which do not accept renderables.

.. index:: single: Properties; Property

.. _Property:

Property
++++++++

The simplest renderable is :class:`Property`, which renders to the value of the property named by its argument::

    from buildbot.plugins import steps, util

    f.addStep(steps.ShellCommand(command=['echo', 'buildername:',
                                 util.Property('buildername')]))

You can specify a default value by passing a ``default`` keyword argument::

    f.addStep(steps.ShellCommand(command=['echo', 'warnings:',
                                 util.Property('warnings', default='none')]))

The default value is used when the property doesn't exist, or when the value is something Python regards as ``False``.
The ``defaultWhenFalse`` argument can be set to ``False`` to force buildbot to use the default argument only if the parameter is not set::

    f.addStep(steps.ShellCommand(command=['echo', 'warnings:',
                                 util.Property('warnings', default='none',
                                               defaultWhenFalse=False)]))

The default value can be a renderable itself, e.g.,

::

    command=util.Property('command', default=util.Property('default-command'))

.. index:: single: Properties; Interpolate

.. _Interpolate:

Interpolate
+++++++++++

:class:`Property` can only be used to replace an entire argument: in the example above, it replaces an argument to ``echo``.
Often, properties need to be interpolated into strings, instead.
The tool for that job is :ref:`Interpolate`.

The more common pattern is to use Python dictionary-style string interpolation by using the ``%(prop:<propname>)s`` syntax.
In this form, the property name goes in the parentheses, as above.
A common mistake is to omit the trailing "s", leading to a rather obscure error from Python ("ValueError: unsupported format character").

::

    from buildbot.plugins import steps, util
    f.addStep(steps.ShellCommand(command=['make',
                                          util.Interpolate('REVISION=%(prop:got_revision)s'),
                                          'dist']))

This example will result in a ``make`` command with an argument like ``REVISION=12098``.

.. _Interpolate-DictStyle:

The syntax of dictionary-style interpolation is a selector, followed by a colon, followed by a selector specific key, optionally followed by a colon and a string indicating how to interpret the value produced by the key.

The following selectors are supported.

``prop``
    The key is the name of a property.

``src``
    The key is a codebase and source stamp attribute, separated by a colon.

``kw``
    The key refers to a keyword argument passed to ``Interpolate``.
    Those keyword arguments may be ordinary values or renderables.

The following ways of interpreting the value are available.

``-replacement``
    If the key exists, substitute its value; otherwise, substitute ``replacement``.
    ``replacement`` may be empty (``%(prop:propname:-)s``).
    This is the default.

``~replacement``
    Like ``-replacement``, but only substitutes the value of the key if it is something Python regards as ``True``.
    Python considers ``None``, 0, empty lists, and the empty string to be false, so such values will be replaced by ``replacement``.

``+replacement``
    If the key exists, substitute ``replacement``; otherwise, substitute an empty string.

``?|sub_if_exists|sub_if_missing``

``#?|sub_if_true|sub_if_false``
    Ternary substitution, depending on either the key being present (with ``?``, similar to ``+``) or being ``True`` (with ``#?``, like ``~``).
    Notice that there is a pipe immediately following the question mark *and* between the two substitution alternatives.
    The character that follows the question mark is used as the delimiter between the two alternatives.
    In the above examples, it is a pipe, but any character other than ``(`` can be used.

.. note::

   Although these are similar to shell substitutions, no other substitutions are currently supported.

Example::

    from buildbot.plugins import steps, util
    f.addStep(steps.ShellCommand(command=['make',
                                          util.Interpolate('REVISION=%(prop:got_revision:-%(src::revision:-unknown)s)s'),
                                          'dist']))

In addition, ``Interpolate`` supports using positional string interpolation.
Here, ``%s`` is used as a placeholder, and the substitutions (which may be renderables), are given as subsequent arguments::

  TODO

.. note::

   Like Python, you can use either positional interpolation *or* dictionary-style interpolation, not both.
   Thus you cannot use a string like ``Interpolate("foo-%(src::revision)s-%s", "branch")``.

.. index:: single: Properties; Renderer

.. _Renderer:

Renderer
++++++++

While Interpolate can handle many simple cases, and even some common conditionals, more complex cases are best handled with Python code.
The ``renderer`` decorator creates a renderable object whose rendering is obtained by calling the decorated function when the step it's passed to begins.
The function receives an :class:`~buildbot.interfaces.IProperties` object, which it can use to examine the values of any and all properties.
For example::

    from buildbot.plugins import steps, util

    @util.renderer
    def makeCommand(props):
        command = ['make']
        cpus = props.getProperty('CPUs')
        if cpus:
            command.extend(['-j', str(cpus+1)])
        else:
            command.extend(['-j', '2'])
        command.extend(['all'])
        return command

    f.addStep(steps.ShellCommand(command=makeCommand))

You can think of ``renderer`` as saying "call this function when the step starts".

.. index:: single: Properties; Transform

.. _Transform:

Transform
+++++++++

``Transform`` is an alternative to ``renderer``.
While ``renderer`` is useful for creating new renderables, ``Transform`` is easier to use when you want to transform or combine the renderings of preexisting ones.

``Transform`` takes a function and any number of positional and keyword arguments.
The function must either be a callable object or a renderable producing one.
When rendered, a ``Transform`` first replaces all of its arguments that are renderables with their renderings, then calls the function, passing it the positional and keyword arguments, and returns the result as its own rendering.

For example, suppose ``my_path`` is a path on the buildslave, and you want to get it relative to the build directory.
You can do it like this::

    import os.path
    from buildbot.plugins import util

    my_path_rel = util.Transform(os.path.relpath, my_path, start=util.Property('builddir'))

This works whether ``my_path`` is an ordinary string or a renderable.
``my_path_rel`` will be a renderable in either case, however.

.. index:: single: Properties; WithProperties

.. _WithProperties:

FlattenList
+++++++++++

If nested list should be flatten for some renderables, FlattenList could be used.
For example::

   f.addStep(ShellCommand(command=[ 'make' ], descriptionDone=FlattenList([ 'make ', [ 'done' ]])))

``descriptionDone`` would be set to ``[ 'make', 'done' ]`` when the ``ShellCommand`` executes.
This is useful when a list-returning property is used in renderables.

.. note::

   ShellCommand automatically flattens nested lists in its ``command`` argument, so there is no need to use ``FlattenList`` for it.

WithProperties
++++++++++++++

.. warning::

    This class is deprecated.
    It is an older version of :ref:`Interpolate`.
    It exists for compatibility with older configs.

The simplest use of this class is with positional string interpolation.
Here, ``%s`` is used as a placeholder, and property names are given as subsequent arguments::

    from buildbot.plugins import steps, util
    f.addStep(steps.ShellCommand(
        command=["tar", "czf",
                 util.WithProperties("build-%s-%s.tar.gz", "branch", "revision"),
                 "source"]))

If this :class:`BuildStep` were used in a tree obtained from Git, it would create a tarball with a name like :file:`build-master-a7d3a333db708e786edb34b6af646edd8d4d3ad9.tar.gz`.

.. index:: unsupported format character

The more common pattern is to use Python dictionary-style string interpolation by using the ``%(propname)s`` syntax.
In this form, the property name goes in the parentheses, as above.
A common mistake is to omit the trailing "s", leading to a rather obscure error from Python ("ValueError: unsupported format character").

::

    from buildbot.plugins import steps, util
    f.addStep(steps.ShellCommand(command=['make',
                                          util.WithProperties('REVISION=%(got_revision)s'),
                                          'dist']))

This example will result in a ``make`` command with an argument like ``REVISION=12098``.

.. _WithProperties-DictStyle:

The dictionary-style interpolation supports a number of more advanced syntaxes in the parentheses.

``propname:-replacement``
    If ``propname`` exists, substitute its value; otherwise, substitute ``replacement``.
    ``replacement`` may be empty (``%(propname:-)s``)

``propname:~replacement``
    Like ``propname:-replacement``, but only substitutes the value of property ``propname`` if it is something Python regards as ``True``.
    Python considers ``None``, 0, empty lists, and the empty string to be false, so such values will be replaced by ``replacement``.

``propname:+replacement``
    If ``propname`` exists, substitute ``replacement``; otherwise, substitute an empty string.

Although these are similar to shell substitutions, no other substitutions are currently supported, and ``replacement`` in the above cannot contain more substitutions.

Note: like Python, you can use either positional interpolation *or* dictionary-style interpolation, not both.
Thus you cannot use a string like ``WithProperties("foo-%(revision)s-%s", "branch")``.

.. _Custom-Renderables:

Custom Renderables
++++++++++++++++++

If the options described above are not sufficient, more complex substitutions can be achieved by writing custom renderables.

The :class:`~buildbot.interfaces.IRenderable` interface is simple - objects must provide a `getRenderingFor` method.
The method should take one argument - an :class:`~buildbot.interfaces.IProperties` provider - and should return the rendered value or a deferred firing with one.
Pass instances of the class anywhere other renderables are accepted.
For example::

    class DetermineFoo(object):
        implements(IRenderable)
        def getRenderingFor(self, props):
            if props.hasProperty('bar'):
                return props['bar']
            elif props.hasProperty('baz'):
                return props['baz']
            return 'qux'
    ShellCommand(command=['echo', DetermineFoo()])

or, more practically,

::

    class Now(object):
        implements(IRenderable)
        def getRenderingFor(self, props):
            return time.clock()
    ShellCommand(command=['make', Interpolate('TIME=%(kw:now)s', now=Now())])

This is equivalent to::

    @renderer
    def now(props):
        return time.clock()
    ShellCommand(command=['make', Interpolate('TIME=%(kw:now)s', now=now)])

Note that a custom renderable must be instantiated (and its constructor can take whatever arguments you'd like), whereas a function decorated with :func:`renderer` can be used directly.
