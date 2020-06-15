.. bb:step:: MaxQ

.. _Step-MaxQ:

MaxQ
++++


MaxQ (http://maxq.tigris.org/) is a web testing tool that allows you to record HTTP sessions and play them back.
The :bb:step:`MaxQ` step runs this framework.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.MaxQ(testdir='tests/'))

The single argument, ``testdir``, specifies where the tests should be run.
This directory will be passed to the ``run_maxq.py`` command, and the results analyzed.
