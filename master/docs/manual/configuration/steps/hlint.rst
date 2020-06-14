.. bb:step:: HLint

.. _Step-HLint:

HLint
+++++

The :bb:step:`HLint` step runs Twisted Lore, a lint-like checker over a set of ``.xhtml`` files.
Any deviations from recommended style is flagged and put in the output log.

The step looks at the list of changes in the build to determine which files to check - it does not check all files.
It specifically excludes any ``.xhtml`` files in the top-level ``sandbox/`` directory.

The step takes a single, optional, parameter: ``python``.
This specifies the Python executable to use to run Lore.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.HLint())
