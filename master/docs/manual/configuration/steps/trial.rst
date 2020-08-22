.. bb:step:: Trial

.. _Step-Trial:

Trial
+++++

.. py:class:: buildbot.steps.python_twisted.Trial

This step runs a unit test suite using :command:`trial`, a unittest-like testing framework that is a component of Twisted Python.

The :bb:step:`Trial` takes the following arguments:

``python``
  (string or list of strings, optional) Which python executable to use.
  Will form the start of the argv array that will launch ``trial``.
  If you use this, you should set ``trial`` to an explicit path (like /usr/bin/trial or ./bin/trial).
  Defaults to ``None``, which leaves it out entirely (running 'trial args' instead of python ./bin/trial args').
  Likely values are ``'python'``, ``['python3.5']``, ``['python', '-Wall']``, etc.

``trial``
  (string, optional) Which 'trial' executable to run
  Defaults to ``'trial'``, which will cause ``$PATH`` to be searched and probably find ``/usr/bin/trial``.
  If you set ``python``, this should be set to an explicit path (because ``python3.5 trial`` will not work).

``trialMode``
  (list of strings, optional) A list of arguments to pass to trial to set the reporting mode.
  This defaults to ``['-to']`` which means 'verbose colorless output' to the trial that comes with Twisted-2.0.x and at least -2.1.0 .
  Newer versions of Twisted may come with a trial that prefers ``['--reporter=bwverbose']``.

``trialArgs``
  (list of strings, optional) A list of arguments to pass to trial.
  This can be used to turn on any extra flags you like.
  Defaults to ``[]``.

``jobs``
  (integer, optional) Defines the number of parallel jobs.

``tests``
  (list of strings, optional) Defines the test modules to run.
  For example, ``['twisted.test.test_defer', 'twisted.test.test_process']``
  If this is a string, it will be converted into a one-item list.

``testChanges``
  (boolean, optional) Selects the tests according to the changes in the Build.
  If set, this will override the ``tests`` parameter and asks the Build for all the files that make up the Changes going into this build.
  The filenames will be passed to ``trial`` asking to run just the tests necessary to cover the changes.

``recurse``
  (boolean, optional) Selects the ``--recurse`` option of trial.
  This allows test cases to be found in deeper subdirectories of the modules listed in ``tests``.
  When using ``testChanges`` this option is not necessary.

``reactor``
  (boolean, optional) Selects the reactor to use within Trial.
  For example, options are ``gtk`` or ``java``.
  If not provided, the Twisted's usual platform-dependent default is used.

``randomly``
  (boolean, optional) If ``True``, adds the ``--random=0`` argument, which instructs trial to run the unit tests in a random order each time.
  This occasionally catches problems that might be  masked when one module always runs before another.

``**kwargs``
  (dict, optional) The step inherits all arguments of ``ShellMixin`` except ``command``.

Trial creates and switches into a directory named :file:`_trial_temp/` before running the tests, and sends the twisted log (which includes all exceptions) to a file named :file:`test.log`.
This file will be pulled up to the master where it can be seen as part of the status output.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Trial(tests='petmail.test'))
