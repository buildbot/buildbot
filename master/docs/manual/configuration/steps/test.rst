.. bb:step:: Test

.. _Step-Test:

Test
++++

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Test())

This is meant to handle unit tests.
The default command is :command:`make test`, and the ``warnOnFailure`` flag is set.
The other arguments are identical to :bb:step:`ShellCommand`.
