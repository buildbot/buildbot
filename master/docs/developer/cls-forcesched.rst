.. -*- rst -*-
.. _ForceScheduler:

ForceScheduler
--------------
This is the developer oriented version of the ForceScheduler documentation

.. py:class:: buildbot.schedulers.forcesched.ForceScheduler

.. py:module:: buildbot.schedulers.forceshed

.. py:class:: IParameter(name, label, type, default, required, multiple, regex)

    The interface that all parameter classes must implement.

    .. py:attribute:: name

           The name of the parameter. Will correspond to the name of the property
   	   that your parameter will set.
	   This name is also used internally as identifier for http POST arguments
    .. py:attribute:: label

           The label of the parameter. ie what is displayed to the user
           you can pass html

    .. py:attribute:: type
	 
           The type of the parameter is used by the jinja template to create
	   appropriate html form widget

    .. py:attribute:: default

           The default value, that is used if there is no user input

    .. py:attribute:: required

           if this bool is set, an error will be shown to user if
	   there is no input in this field

    .. py:attribute:: multiple

           if true, this field is a list of value (e.g. list of tests to run)

    .. py:attribute:: regex

           a string that will be compiled as a regex, and used to validate 
	   the input of this parameter

    .. py:method:: update_from_post(self, master, properties, changes, req):

        .. py:attribute:: master

    	       the master object

        .. py:attribute:: properties

    	       a dictionnary of properties that can be updated depending on
	       if the parameter is in the POST arguments list

        .. py:attribute:: changes

    	       a parameter can also modify the sourcestamp by adding changids
	       to this list of changes

        .. py:attribute:: req

    	       the http request where the parameter can look for its values.
	      
.. py:class:: BaseParameter(name, label, type, default, required, multiple, regex)

   This is the base implementation for most parameters, it will check validity,
   ensure the arg is present if required flag is set, and implement the default
   value. It will finally call a translation method that converts the string(s)
   from POST to a python object.

    .. py:method:: parse_from_args(self, l)

       return the list of object corresponding to the list or string passed
       default function will just call :py:func:`parse_from_first_arg` with the 
       first argument

    .. py:method:: parse_from_first_arg(self, s)

       return the  object corresponding to the string passed
       default function will just return the unmodified string

.. py:class:: FixedParameter(name, label, default)

   This parameter will not be shown on the web form, and always generate a 
   property with its default value

.. py:class:: StringParameter(name, label, default, regex, size=10)

   This parameter will show a textentry.
   The size of the input field can be customized
       
.. py:class:: TextParameter(name, label, default, regex, cols=80, rows=20)

   Represent a string forced build parameter
   regular expression validation is optionally done
   it is represented by a textarea
   extra parameter cols, and rows are available to the template system
   
   this can be subclassed in order to have more customization
   e.g. 

   	* developer could send a list of git branch to pull from

	* developer could send a list of gerrit changes to cherry-pick, 

	* developer could send a shell script to amend the build.

   beware of security issues anyway.

   .. py:attribute:: cols

      the number of columns textarea will have

   .. py:attribute:: rows

      the number of rows textarea will have

   .. py:method:: value_to_text(self, value)

      format value up to original text

.. py:class:: IntParameter(name, label, default)

   a simple conversion from string to integer for a integer parameter

.. py:class:: BooleanParameter(name, label, default)

   Represent a boolean forced build parameter
   will be presented as a checkbox

.. py:class:: UserNameParameter(name, label, default, size=30, need_email=True)

   Represent a username in the form "User <email@email.com>" 
   By default, this ensure that the user provided an email

   .. py:attribute:: need_email

      change to False if we just want to accept arbitrary username

.. py:class:: ChoiceStringParameter(name, label, default, choices=[], strict=True, multiple=False)

   Let the user choose between several choices (e.g the list of branch
   you are supporting, or the test campaign to run)

   .. py:attribute:: choices

      The list of available choices

   .. py:attribute:: strict

      verify that the user input is from the list. 
      NB: User cannot choose option out of the choice list in the webui, 
      but could craft an http post request.

   .. py:attribute:: multiple

      will chance the html form to allow the user to select several options

.. py:class:: InheritBuildParameter(name, label, compatible_builds)

      a special parameter for inheriting force builds parameters from 
      another build.

   .. py:attribute:: compatible_builds

      a function provided by config that will find compatible build in
       the build history

   .. py:method:: compatible_builds(masterstatus, buildername)

      .. py:attribute:: masterstatus

      	 The master status, where you can get the list of previous builds

      .. py:attribute:: buildername

	 the name of the builder (can be None in case of ForceAllBuild Form)

.. py:class:: AnyPropertyParameter(name, label)

   a parameter for setting arbitrary property in the build
   a bit atypical, as it will generate two fields in the html form
   This Parameter is here to reimplement old buildbot behavior, and should
   be avoided. Stricter parameter name and type shoud be preferred.
