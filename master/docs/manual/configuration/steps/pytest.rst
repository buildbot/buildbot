.. bb:step:: Pytest

.. _Step-Pytest:

Pytest
++++++

The :bb:step:`Pytest` step runs the Python test suite with `pytest <https://pytest.org>`_ and
parses the test counts from its output.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Pytest())

The default command is ``python -m pytest``; pass ``command`` to customize it, e.g. to select the
tests to run or to run pytest from a virtualenv:

.. code-block:: python

    f.addStep(steps.Pytest(command=["venv/bin/python", "-m", "pytest", "tests/"]))

The step parses the final summary line of the pytest output (e.g. ``2 failed, 3 passed, 1 warning
in 12.34s``) and displays the counts in the step summary. The counts are also stored as the step
statistics ``tests-total``, ``tests-passed``, ``tests-failed``, ``tests-errors``,
``tests-skipped``, ``tests-xfailed``, ``tests-xpassed``, ``tests-warnings`` and
``tests-deselected``. ``tests-total`` counts the tests that pytest collected and ran, so it does
not include warnings and deselected tests.

The result of the step follows the pytest exit code: success when all tests passed, failure when
tests failed or no tests were collected, and exception when pytest was interrupted, hit an
internal error or was invoked incorrectly. The mapping can be customized with the ``decodeRC``
argument:

.. code-block:: python

    from buildbot.process import results

    # treat "no tests collected" as success
    f.addStep(steps.Pytest(decodeRC={0: results.SUCCESS, 5: results.SUCCESS}))

In addition, the step accepts all arguments of the :bb:step:`ShellCommand` step.

.. note::

   The step parses the plain text output of pytest.
   Options that change the output format, disable the summary line (e.g. ``-q`` keeps it, but
   ``--no-summary`` style plugins may not) or enable colored output when not attached to a
   terminal may prevent the counts from being detected.
