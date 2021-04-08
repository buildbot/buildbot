.. bb:step:: Cppcheck

.. _Step-Cppcheck:

Cppcheck
++++++++

This step runs ``cppcheck``, analyse its output, and set the outcome in :ref:`Properties`.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Cppcheck(enable=['all'], inconclusive=True]))

This class adds the following arguments:

``binary``
    (Optional, defaults to ``cppcheck``)
    Use this if you need to give the full path to the cppcheck binary or if your binary is called differently.

``source``
    (Optional, defaults to ``['.']``)
    This is the list of paths for the sources to be checked by this step.

``enable``
    (Optional)
    Use this to give a list of the message classes that should be in cppcheck report.
    See the cppcheck man page for more information.

``inconclusive``
    (Optional)
    Set this to ``True`` if you want cppcheck to also report inconclusive results.
    See the cppcheck man page for more information.

``extra_args``
    (Optional)
    This is the list of extra arguments to be given to the cppcheck command.

All other arguments are identical to :bb:step:`ShellCommand`.
