.. bb:step:: DebLintian

.. _Step-DebLintian:

DebLintian
++++++++++

The :bb:step:`DebLintian` step checks a build .deb for bugs and policy violations.
The packages or changes file to test is specified in ``fileloc``

.. code-block:: python

    from buildbot.plugins import steps, util

    f.addStep(steps.DebLintian(fileloc=util.Interpolate("%(prop:deb-changes)s")))
