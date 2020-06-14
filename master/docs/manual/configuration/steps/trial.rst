.. bb:step:: Trial

.. _Step-Trial:

Trial
+++++

.. py:class:: buildbot.steps.python_twisted.Trial

This step runs a unit test suite using :command:`trial`, a unittest-like testing framework that is a component of Twisted Python.
Trial is used to implement Twisted's own unit tests, and is the unittest-framework of choice for many projects that use Twisted internally.

Projects that use trial typically have all their test cases in a 'test' subdirectory of their top-level library directory.
For example, for a package ``petmail``, the tests might be in :file:`petmail/test/test_*.py`.
More complicated packages (like Twisted itself) may have multiple test directories, like :file:`twisted/test/test_*.py` for the core functionality and :file:`twisted/mail/test/test_*.py` for the email-specific tests.

To run trial tests manually, you run the :command:`trial` executable and tell it where the test cases are located.
The most common way of doing this is with a module name.
For petmail, this might look like :command:`trial petmail.test`, which would locate all the :file:`test_*.py` files under :file:`petmail/test/`, running every test case it could find in them.
Unlike the ``unittest.py`` that comes with Python, it is not necessary to run the :file:`test_foo.py` as a script; you always let trial do the importing and running.
The step's ``tests``` parameter controls which tests trial will run: it can be a string or a list of strings.

To find the test cases, the Python search path must allow something like ``import petmail.test`` to work.
For packages that don't use a separate top-level :file:`lib` directory, ``PYTHONPATH=.`` will work, and will use the test cases (and the code they are testing) in-place.
``PYTHONPATH=build/lib`` or ``PYTHONPATH=build/lib.somearch`` are also useful when you do a ``python setup.py build`` step first.
The ``testpath`` attribute of this class controls what :envvar:`PYTHONPATH` is set to before running :command:`trial`.

Trial has the ability, through the ``--testmodule`` flag, to run only the set of test cases named by special ``test-case-name`` tags in source files.
We can get the list of changed source files from our parent Build and provide them to trial, thus running the minimal set of test cases needed to cover the Changes.
This is useful for quick builds, especially in trees with a lot of test cases.
The ``testChanges`` parameter controls this feature: if set, it will override ``tests``.

The trial executable itself is typically just :command:`trial`, and is typically found in the shell search path.
It can be overridden with the ``trial`` parameter.
This is useful for Twisted's own unittests, which want to use the copy of bin/trial that comes with the sources.

To influence the version of Python being used for the tests, or to add flags to the command, set the ``python`` parameter.
This can be a string (like ``python2.2``) or a list (like ``['python2.3', '-Wall']``).

Trial creates and switches into a directory named :file:`_trial_temp/` before running the tests, and sends the twisted log (which includes all exceptions) to a file named :file:`test.log`.
This file will be pulled up to the master where it can be seen as part of the status output.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Trial(tests='petmail.test'))

Trial has the ability to run tests on several workers in parallel (beginning with Twisted 12.3.0).
Set ``jobs`` to the number of workers you want to run.
Note that running :command:`trial` in this way will create multiple log files (named :file:`test.N.log`, :file:`err.N.log` and :file:`out.N.log` starting with ``N=0``) rather than a single :file:`test.log`.

This step takes the following arguments:

``jobs``
   (optional) Number of worker-resident trial workers to use when running the tests.
   Defaults to 1 worker.
   Only works with Twisted>=12.3.0.
