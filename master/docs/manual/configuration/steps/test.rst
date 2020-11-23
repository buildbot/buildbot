.. bb:step:: Test

.. _Step-Test:

Test
++++

.. note::

    This step is being migrated to :ref:`new-style<New-Style-Build-Steps>`.
    A new-style equivalent is provided as ``TestNewStyle``.
    This should be inherited by any custom steps until :ref:`Buildbot 3.0 is released<3.0_Upgrading>`.
    Regular uses without inheritance are not affected.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Test())

This is meant to handle unit tests.
The default command is :command:`make test`, and the ``warnOnFailure`` flag is set.
The other arguments are identical to :bb:step:`ShellCommand`.
