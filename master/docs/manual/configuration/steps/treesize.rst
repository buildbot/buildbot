.. bb:step:: TreeSize

.. index:: Properties; tree-size-KiB

.. _Step-TreeSize:

TreeSize
++++++++

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.TreeSize())

This is a simple command that uses the :command:`du` tool to measure the size of the code tree.
It puts the size (as a count of 1024-byte blocks, aka 'KiB' or 'kibibytes') on the step's status text, and sets a build property named ``tree-size-KiB`` with the same value.
All arguments are identical to :bb:step:`ShellCommand`.
