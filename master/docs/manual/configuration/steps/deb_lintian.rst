.. bb:step:: DebLintian

.. _Step-DebLintian:

DebLintian
++++++++++

The :bb:step:`DebLintian` step checks a build .deb for bugs and policy violations.
The packages or changes file to test is specified in ``fileloc``.

.. code-block:: python

    from buildbot.plugins import steps, util

    f.addStep(steps.DebLintian(fileloc=util.Interpolate("%(prop:deb-changes)s")))

This class adds the following arguments:

``fileloc``
    (Optional, string)
    Location of the .deb or .changes files to test.

``suppressTags``
    (Optional, list of strings)
    List of tags to suppress.

All other arguments are identical to :bb:step:`ShellCommand`.
