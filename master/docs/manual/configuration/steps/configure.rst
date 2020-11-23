.. bb:step:: Configure

.. _Step-Configure:

Configure
+++++++++

.. py:class:: buildbot.steps.shell.Configure

.. note::

    This step is being migrated to :ref:`new-style<New-Style-Build-Steps>`.
    A new-style equivalent is provided as ``ConfigureNewStyle``.
    This should be inherited by any custom steps until :ref:`Buildbot 3.0 is released<3.0_Upgrading>`.
    Regular uses without inheritance are not affected.

This is intended to handle the :command:`./configure` step from autoconf-style projects, or the ``perl Makefile.PL`` step from perl :file:`MakeMaker.pm`-style modules.
The default command is :command:`./configure` but you can change this by providing a ``command=`` parameter.
The arguments are identical to :bb:step:`ShellCommand`.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Configure())
