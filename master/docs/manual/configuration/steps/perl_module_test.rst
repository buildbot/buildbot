.. bb:step:: PerlModuleTest

.. _Step-PerlModuleTest:

PerlModuleTest
++++++++++++++

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.PerlModuleTest())

This is a simple command that knows how to run tests of perl modules.
It parses the output to determine the number of tests passed and failed and total number executed, saving the results for later query.
The command is ``prove --lib lib -r t``, although this can be overridden with the ``command`` argument.
All other arguments are identical to those for :bb:step:`ShellCommand`.
