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
-----------------------

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

Using Properties in Steps
-------------------------

For the most part, properties are used to alter the behavior of build steps
during a build.  This is done by annotating the step definition in
``master.cfg`` with placeholders.  When the step is executed, these
placeholders will be replaced using the current values of the build properties.

.. note:: Properties are defined while a build is in progress; their values are
    not available when the configuration file is parsed.  This can sometimes
    confuse newcomers to Buildbot!  In particular, the following is a common error::

        if Property('release_train') == 'alpha':
            f.addStep(...)

    This does not work because the value of the property is not available when
    the ``if`` statement is executed.  However, Python will not detect this as
    an error - you will just never see the step added to the factory.

You can use build properties in most step paramaters.  Please file bugs for any
parameters which do not accept properties.

.. index:: single: Properties; Property

.. _Property:

Property
++++++++

The simplest form of annotation is to wrap the property name with
:class:`Property`::

   from buildbot.steps.shell import ShellCommand
   from buildbot.process.properties import Property

   f.addStep(ShellCommand(command=[ 'echo', 'buildername:', Property('buildername') ]))

You can specify a default value by passing a ``default`` keyword argument::

   f.addStep(ShellCommand(command=[ 'echo', 'warnings:',
                                    Property('warnings', default='none') ]))

The default value is used when the property doesn't exist, or when the value is
something Python regards as ``False``. The ``defaultWhenFalse`` argument can be
set to ``False`` to force buildbot to use the default argument only if the
parameter is not set::

   f.addStep(ShellCommand(command=[ 'echo', 'warnings:',
                    Property('warnings', default='none', defaultWhenFalse=False) ]))

The default value can reference other properties, e.g., ::

    command=Property('command', default=Property('default-command'))


.. Index:: single; Properties; WithProperties

.. _WithProperties:

WithProperties
++++++++++++++

:class:`Property` can only be used to replace an entire argument: in the
example above, it replaces an argument to ``echo``.  Often, properties need to
be interpolated into strings, instead.  The tool for that job is
:class:`WithProperties`. 

The simplest use of this class is with positional string interpolation.  Here,
``%s`` is used as a placeholder, and property names are given as subsequent
arguments::

    from buildbot.steps.shell import ShellCommand
    from buildbot.process.properties import WithProperties
    f.addStep(ShellCommand(
              command=["tar", "czf",
                       WithProperties("build-%s-%s.tar.gz", "branch", "revision"),
                       "source"]))

If this :class:`BuildStep` were used in a tree obtained from Git, it would
create a tarball with a name like
:file:`build-master-a7d3a333db708e786edb34b6af646edd8d4d3ad9.tar.gz`.

.. index:: unsupported format character

The more common pattern is to use python dictionary-style string interpolation
by using the ``%(propname)s`` syntax. In this form, the property name goes in
the parentheses, as above.  A common mistake is to omit the trailing "s",
leading to a rather obscure error from Python ("ValueError: unsupported format
character"). ::

   from buildbot.steps.shell import ShellCommand
   from buildbot.process.properties import WithProperties
   f.addStep(ShellCommand(command=[ 'make', WithProperties('REVISION=%(got_revision)s'),
                                    'dist' ]))

This example will result in a ``make`` command with an argument like
``REVISION=12098``.

.. _WithProperties-DictStyle:

The dictionary-style interpolation supports a number of more advanced
syntaxes in the parentheses.

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

``propname:?:sub_if_true:sub_if_false``

``propname:#?:sub_if_exists:sub_if_missing``
    Ternary substitution, depending on either ``propname`` being ``True`` (with
    ``:?``, similar to ``:~``) or being present (with ``:#?``, like ``:+``).
    Notice that there is a colon immediately following the question mark *and*
    between the two substitution alternatives. The character that follows the
    question mark is used as the delimeter between the two alternatives. In the
    above examples, it is a colon, but any single character can be used.
    
    
Although these are similar to shell substitutions, no other
substitutions are currently supported, and ``replacement`` in the
above cannot contain more substitutions.

Note: like python, you can use either positional interpolation *or*
dictionary-style interpolation, not both. Thus you cannot use a string like
``WithProperties("foo-%(revision)s-%s", "branch")``.

.. Index:: single; Properties; WithSource

.. _WithSource:

WithSource
++++++++++

A build may contain more than one sourcestamp. Buildsteps may need information 
from a sourcestamp like repository or branch to be able to perform their task.
The class :class:`WithSource` interpolates the atrributes from a single sourcestamp
into a string that can be used by a buildstep. 

The simplest use of this class is with positional string interpolation.  Here,
``%s`` is used as a placeholder, and attribute names are given as subsequent
arguments::

    from buildbot.steps.shell import ShellCommand
    from buildbot.process.properties import WithSource
    f.addStep(ShellCommand(
              command=["tar", "czf",
                       WithSource("mailexe","mailer-%s-%s.tar.gz", "branch", "revision"),
                       "source"]))
    
In this example 'mailexe' is the codebase for the mail application. Branch and revision
are the attibute names inside the sourcestamp that belongs to the application.

.. index:: unsupported format character

The more common pattern is to use python dictionary-style string interpolation
by using the ``%(propname)s`` syntax. In this form, the property name goes in
the parentheses, as above.  A common mistake is to omit the trailing "s",
leading to a rather obscure error from Python ("ValueError: unsupported format
character")::

   from buildbot.steps.shell import ShellCommand
   from buildbot.process.properties import WithSource
   f.addStep(ShellCommand(command=[ 'make', WithSource('mailexe','REVISION=%(revision)s'),
                                    'dist' ]))

This example will result in a ``make`` command with an argument like
``REVISION=12098``.

The :ref:`dictionary style<WithProperties-DictStyle>` interpolation supports a number of more advanced
syntaxes in the parentheses.
