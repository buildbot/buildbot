.. bb:step:: PyLint

.. _Step-PyLint:

PyLint
++++++

Similarly, the :bb:step:`PyLint` step will run :command:`pylint` and analyze the results.

You must supply the command line to be used.
There is no default.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.PyLint(command=["pylint", "src"]))

This step takes the following arguments:

``store_results``
   (optional) Boolean, ``true`` if the test results should be stored in the test database.
   The default value is ``true``.
