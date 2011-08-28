.. index:: Properties

.. _Properties:

Properties
==========

Build properties are a generalized way to provide configuration information to
build steps; see :ref:`Build-Properties` for the conceptual overview of
properties.

Some build properties come from external sources and are set before the build
begins; others are set during the build, and available for later steps.  The
sources for properties are:

* :bb:cfg:`global configuration <properties>` -- These properties apply to all
  builds.
* :ref:`schedulers <Configuring-Schedulers>` -- A scheduler can specify
  properties that become available to all builds it starts.
* :ref:`changes <Change-Sources>` -- A change can have properties attached to
  it, supplying extra information gathered by the change source.  This is most
  commonly used with the :bb:cmdline:`sendchange` command.
* :bb:status:`forced builds <WebStatus>` -- The "Force Build" form allows users
  to specify properties
* :bb:cfg:`buildslaves <slaves>` -- A buildslave can pass properties on to
  the builds it performs.
* :ref:`builds <Common-Build-Properties>` -- A build automatically sets a
  number of properties on itself.
* :bb:cfg:`builders <builders>` -- A builder can set properties on all the
  builds it runs.
* :ref:`steps <Build-Steps>` -- The steps of a build can set properties that
  are available to subsequent steps.  In particular, source steps set a number
  of properties.

If the same property is supplied in multiple places, the final appearance takes
precedence.  For example, a property set in a builder configuration will
override one supplied by a scheduler.

Properties are stored internally in JSON format, so they are limited to basic
types of data: numbers, strings, lists, and dictionaries.

.. index:: single: Properties; Common Properties

.. _Common-Build-Properties:

Common Build Properties
+++++++++++++++++++++++

The following build properties are set when the build is started, and
are available to all steps.

.. index:: single: Properties; branch

``branch``
    This comes from the build's :class:`SourceStamp`, and describes which branch is
    being checked out. This will be ``None`` (which interpolates into
    ``WithProperties`` as an empty string) if the build is on the
    default branch, which is generally the trunk. Otherwise it will be a
    string like ``branches/beta1.4``. The exact syntax depends upon the VC
    system being used.

.. index:: single: Properties; revision

``revision``
    This also comes from the :class:`SourceStamp`, and is the revision of the source code
    tree that was requested from the VC system. When a build is requested of a
    specific revision (as is generally the case when the build is triggered by
    Changes), this will contain the revision specification. This is always a
    string, although the syntax depends upon the VC system in use: for SVN it is an
    integer, for Mercurial it is a short string, for Darcs it is a rather large
    string, etc.
    
    If the :guilabel:`force build` button was pressed, the revision will be ``None``,
    which means to use the most recent revision available.  This is a `trunk
    build`. This will be interpolated as an empty string.

.. index:: single: Properties; got_revision

``got_revision``
    This is set when a :class:`Source` step checks out the source tree, and
    provides the revision that was actually obtained from the VC system.
    In general this should be the same as ``revision``, except for
    trunk builds, where ``got_revision`` indicates what revision was
    current when the checkout was performed. This can be used to rebuild
    the same source code later.
    
    .. note:: For some VC systems (Darcs in particular), the revision is a
       large string containing newlines, and is not suitable for interpolation
       into a filename.

.. index:: single: Properties; buildername

``buildername``
    This is a string that indicates which :class:`Builder` the build was a part of.
    The combination of buildername and buildnumber uniquely identify a
    build.

.. index:: single: Properties; buildnumber

``buildnumber``
    Each build gets a number, scoped to the :class:`Builder` (so the first build
    performed on any given :class:`Builder` will have a build number of 0). This
    integer property contains the build's number.

.. index:: single: Properties; slavename

``slavename``
    This is a string which identifies which buildslave the build is
    running on.

.. index:: single: Properties; scheduler

``scheduler``
    If the build was started from a scheduler, then this property will
    contain the name of that scheduler.

.. index:: single: Properties; repository

``repository``
    The repository of the sourcestamp for this build

.. index:: single: Properties; project

``project``
    The project of the sourcestamp for this build

.. index:: single: Properties; workdir

``workdir``
    The absolute path of the base working directory on the slave, of the current
    builder.

.. index:: single: Properties; Property

.. _Property:

Property
++++++++

You can use build properties in most step paramaters.  Please file bugs for any
parameters which do not accept properties.  The simplest form is to wrap the
property name with :class:`Property`, passing an optional default
argument. ::

   from buildbot.steps.trigger import Trigger
   form buildbot.process.properties import Property

   f.addStep(Trigger(waitForFinish=False, schedulerNames=['build-dependents'], alwaysUseLatest=True,
             set_properties=@{'coq_revision': Property("got_revision")@}))

You can specify a default value by passing a ``default`` argument to
:class:`Property`. This is normally used when the property doesn't exist,
or when the value is something Python regards as ``False``. The ``defaultWhenFalse``
argument can be used to force buildbot to use the default argument only
if the parameter is not set.

.. Index:: single; Properties; WithProperty

.. _WithProperties:

WithProperties
++++++++++++++

You can use build properties in :class:`ShellCommand`\s by using the
``WithProperties`` wrapper when setting the arguments of
the :class:`ShellCommand`. This interpolates the named build properties
into the generated shell command.  Most step parameters accept
``WithProperties``.

You can use python dictionary-style string interpolation by using
the ``%(propname)s`` syntax. In this form, the property name goes
in the parentheses::

    from buildbot.steps.shell import ShellCommand
    from buildbot.process.properties import WithProperties
    
    f.addStep(ShellCommand(
              command=["tar", "czf",
                       WithProperties("build-%s.tar.gz", "revision"),
                       "source"]))

If this :class:`BuildStep` were used in a tree obtained from Subversion, it
would create a tarball with a name like :file:`build-1234.tar.gz`.

Don't forget the extra ``s`` after the closing parenthesis! This is
the cause of many confusing errors.

The dictionary-style interpolation supports a number of more advanced
syntaxes, too.

``propname:-replacement``
    If ``propname`` exists, substitute its value; otherwise,
    substitute ``replacement``. ``replacement`` may be empty
    (``%(propname:-)s``)

``propname:~replacement``
    Like ``propname:-replacement``, but only substitutes the value
    of property ``propname`` if it is something Python regards as ``True``.
    Python considers ``None``, 0, empty lists, and the empty string to be 
    false, so such values will be replaced by ``replacement``.

``propname:+replacement``
    If ``propname`` exists, substitute ``replacement``; otherwise,
    substitute an empty string.

Although these are similar to shell substitutions, no other
substitutions are currently supported, and ``replacement`` in the
above cannot contain more substitutions.

Note: like python, you can either do positional-argument interpolation
*or* keyword-argument interpolation, not both. Thus you cannot use
a string like ``WithProperties("foo-%(revision)s-%s", "branch")``.


Callables
#########

If you need to do more complex substitution, you can pass keyword
arguments to ``WithProperties``. The value of each keyword argument
should be a function that takes one argument (the existing properties)
and returns a string value that will be used to replace that key::

    WithProperties('%(now)s', now=lambda _: time.clock())

    def determine_foo(props):
        if props.hasProperty('bar'):
            return props['bar']
        elif props.hasProperty('baz'):
            return props['baz']
        return 'qux'

    WithProperties('%(foo)s', foo=determine_foo)

Properties Objects
##################

.. class:: buildbot.interfaces.IProperties

   The available methods on a properties object are those described by the
   ``IProperties`` interface.  Specifically:


   .. method:: getProperty(propname, default=None)

      Get a named property, returning the default value if the property is not found.

   .. method:: hasProperty(propname)

      Determine whether the named property exists.

   .. method:: setProperty(propname, value, source)

      Set a property's value, also specifying the source for this value.

   .. method:: getProperties()

      Get a :class:`buildbot.process.properties.Properties` instance.  The
      interface of this class is not finalized; where possible, use the other
      ``IProperties`` methods.

Positional Arguments
####################

The :func:`WithProperties` function also does ``printf``\-style string
interpolation with positional arguments, using strings obtained by calling
``props.getProperty(propname)``. Note that for every ``%s`` (or
``%d``, etc), you must have exactly one additional argument to
indicate which build property you want to insert. ::

    from buildbot.steps.shell import ShellCommand
    from buildbot.process.properties import WithProperties

    f.addStep(ShellCommand(
              command=["tar", "czf",
                       WithProperties("build-%s.tar.gz", "revision"),
                       "source"]))

.. note:: like python, you can either do positional-argument interpolation
   *or* keyword-argument interpolation, not both. Thus you cannot use
   a string like ``WithProperties("foo-%(revision)s-%s", "branch")``.

Properties in Custom Steps
++++++++++++++++++++++++++

In custom :class:`BuildSteps`, you can get and set the build properties with
the :meth:`getProperty`/:meth:`setProperty` methods. Each takes a string
for the name of the property, and returns or accepts an
arbitrary object. For example::

    class MakeTarball(ShellCommand):
        def start(self):
            if self.getProperty("os") == "win":
                self.setCommand([ ... ]) # windows-only command
            else:
                self.setCommand([ ... ]) # equivalent for other systems
            ShellCommand.start(self)

