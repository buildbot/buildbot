.. bb:step:: SubunitShellCommand

.. _Step-SubunitShellCommand:

SubunitShellCommand
+++++++++++++++++++

.. py:class:: buildbot.steps.subunit.SubunitShellCommand

This buildstep is similar to :bb:step:`ShellCommand`, except that it runs the log content through a subunit filter to extract test and failure counts.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.SubunitShellCommand(command="make test"))

This runs ``make test`` and filters it through subunit.
The 'tests' and 'test failed' progress metrics will now accumulate test data from the test run.

If ``failureOnNoTests`` is ``True``, this step will fail if no test is run.
By default ``failureOnNoTests`` is False.
