.. -*- rst -*-
.. _ForceScheduler:

ForceScheduler
--------------

The force scheduler has a symbiotic relationship with the web status, so it
deserves some further description.

Parameters
~~~~~~~~~~

The force scheduler comes with a fleet of parameter classes.  This section
contains information to help users or developers who are interested in adding
new parameter types or hacking the existing types.

.. py:module:: buildbot.schedulers.forceshed

.. py:class:: BaseParameter(name, label, regex, **kwargs)

   This is the base implementation for most parameters, it will check validity,
   ensure the arg is present if the :py:attr:`~IParameter.required` attribute
   is set, and implement the default value.  It will finally call
   :py:meth:`~IParameter.update_from_post` to process the string(s) from the
   HTTP POST.

   This class implements :py:class:`IParameter`, and subclasses are expected to
   adhere to that interface.

   The :py:class:`BaseParameter` constructor converts any keyword arguments
   into instance attributes, so it is generally not necessary for subclasses to
   implement a constructor.

    .. py:method:: update_from_post(master, properties, changes, req)

        :param master: the :py:class:`~buildbot.master.BuildMaster` instance
        :param properties: a dictionary of properties
        :param changes: a list of changeids that will be used to build the
            SourceStamp for the forced builds
        :param req: the Twisted Web request object

        This method updates ``properties`` and/or ``changes`` according to the
        request.  The default implementation is good for many simple uses, but
        can be overridden for more complex purposes.

    The remaining attributes and methods should be overridden by subclasses, although
    :py:class:`BaseParameter` provides appropriate defaults.

    .. py:attribute:: name

           The name of the parameter. This will correspond to the name of the
           property that your parameter will set.  This name is also used
           internally as identifier for http POST arguments

    .. py:attribute:: label

           The label of the parameter, as displayed to the user.  This value
           can contain raw HTML.

    .. py:attribute:: type

           The type of the parameter is used by the jinja template to create
           appropriate html form widget.  The available values are visible in
           :bb:src:`master/buildbot/status/web/template/forms.html` in the
           ``force_build_one_scheduler`` macro.

    .. py:attribute:: default

           The default value, used if there is no user input.  This is also
           used to fill in the form presented to the user.

    .. py:attribute:: required

           If true, an error will be shown to user if there is no input in this
           field

    .. py:attribute:: multiple

           If true, this parameter will return a list of values (e.g. list of
           tests to run)

    .. py:attribute:: regex

           A string that will be compiled as a regex and used to validate the
           string value of this parameter.  If None, then no validation will
           take place.

    .. py:method:: parse_from_args(l)

       return the list of object corresponding to the list or string passed
       default function will just call :py:func:`parse_from_arg` with the
       first argument

    .. py:method:: parse_from_arg(s)

       return the  object corresponding to the string passed
       default function will just return the unmodified string


