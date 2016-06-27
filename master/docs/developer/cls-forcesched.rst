.. -*- rst -*-
.. _ForceScheduler:

ForceScheduler
--------------

The force scheduler has a symbiotic relationship with the web application, so it deserves some further description.

Parameters
~~~~~~~~~~

The force scheduler comes with a fleet of parameter classes.
This section contains information to help users or developers who are interested in adding new parameter types or hacking the existing types.

.. py:module:: buildbot.schedulers.forceshed

.. py:class:: BaseParameter(name, label, regex, **kwargs)

   This is the base implementation for most parameters, it will check validity, ensure the arg is present if the :py:attr:`~BaseParameter.required` attribute is set, and implement the default value.
   It will finally call :py:meth:`~BaseParameter.updateFromKwargs` to process the string(s) from the HTTP POST.

   The :py:class:`BaseParameter` constructor converts all keyword arguments into instance attributes, so it is generally not necessary for subclasses to implement a constructor.

   For custom parameters that set properties, one simple customization point is `getFromKwargs`:

    .. py:method:: getFromKwargs(kwargs)

        :param kwargs: a dictionary of the posted values

        Given the passed-in POST parameters, return the value of the property that should be set.

   For more control over parameter parsing, including modifying sourcestamps or changeids, override the ``updateFromKwargs`` function, which is the function that :py:class:`ForceScheduler` invokes for processing:

    .. py:method:: updateFromKwargs(master, properties, changes, sourcestamps, collector, kwargs)

        :param master: the :py:class:`~buildbot.master.BuildMaster` instance
        :param properties: a dictionary of properties
        :param changes: a list of changeids that will be used to build the SourceStamp for the forced builds
        :param sourcestamps: the SourceStamp dictionary that will be passed to the build; some parameters modify sourcestamps rather than properties.
        :param collector: a :py:class:`buildbot.schedulers.forcesched.ValidationErrorCollector` object, which is used by nestedParameter to collect errors from its childs
        :param kwargs: a dictionary of the posted values

        This method updates ``properties``, ``changes``,  and/or ``sourcestamps`` according to the request.
        The default implementation is good for many simple uses, but can be overridden for more complex purposes.

        When overriding this function, take all parameters by name (not by position), and include an ``**unused`` catch-all to guard against future changes.

    The remaining attributes and methods should be overridden by subclasses, although :py:class:`BaseParameter` provides appropriate defaults.

    .. py:attribute:: name

           The name of the parameter.
           This corresponds to the name of the property that your parameter will set.
           This name is also used internally as identifier for http POST arguments

    .. py:attribute:: label

           The label of the parameter, as displayed to the user.
           This value can contain raw HTML.

    .. py:method:: fullName

           A fully-qualified name that uniquely identifies the parameter in the scheduler.
           This name is used internally as the identifier for HTTP POST arguments.
           It is a mix of `name` and the parent's `name` (in the case of nested parameters).
           This field is not modifiable.

    .. py:attribute:: type

           A string identifying the type that the parameter conforms to.
           It is used by the angular application to find which angular directive to use for showing the form widget.
           The available values are visible in :src:`www/base/src/app/common/directives/forcefields/forcefields.directive.coffee`.

           Examples of how to create a custom parameter widgets are available in the buildbot source code in directories:

           * :src:`www/codeparameter`

           * :src:`www/nestedexample`

    .. py:attribute:: default

           The default value to use if there is no user input.
           This is also used to fill in the form presented to the user.

    .. py:attribute:: required

           If true, an error will be shown to user if there is no input in this field

    .. py:attribute:: multiple

           If true, this parameter represents a list of values (e.g. list of tests to run)

    .. py:attribute:: regex

           A string that will be compiled as a regex and used to validate the string value of this parameter.
           If None, then no validation will take place.

    .. py:method:: parse_from_args(l)

       return the list of object corresponding to the list or string passed default function will just call :py:func:`parse_from_arg` with the first argument

    .. py:method:: parse_from_arg(s)

       return the  object corresponding to the string passed default function will just return the unmodified string


Nested Parameters
~~~~~~~~~~~~~~~~~

The :py:class:`NestedParameter` class is a container for parameters.
The original motivating purpose for this feature is the multiple-codebase configuration, which needs to provide the user with a form to control the branch (et al) for each codebase independently.
Each branch parameter is a string field with name 'branch' and these must be disambiguated.

In Buildbot nine, this concept has been extended to allow grouping different parameters into UI containers.
Details of the available layouts is described in :ref:`NestedParameter <ForceScheduler-Parameters>`.

Each of the child parameters mixes in the parent's name to create the fully qualified ``fullName``.
This allows, for example, each of the 'branch' fields to have a unique name in the POST request.
The `NestedParameter` handles adding this extra bit to the name to each of the children.
When the `kwarg` dictionary is posted back, this class also converts the flat POST dictionary into a richer structure that represents the nested structure.

As illustration, if the nested parameter has the name 'foo', and has children 'bar1' and 'bar2', then the POST will have entries like "foo.bar1" and "foo.bar2".
The nested parameter will translate this into a dictionary in the 'kwargs' structure, resulting in something like::

    kwargs = {
        # ...
        'foo': {
            'bar1': '...',
            'bar2': '...'
        }
    }

Arbitrary nesting is allowed and results in a deeper dictionary structure.

Nesting can also be used for presentation purposes.
If the name of the :py:class:`NestedParameter` is empty, the nest is "anonymous" and does not mangle the child names.
However, in the HTML layout, the nest will be presented as a logical group.
