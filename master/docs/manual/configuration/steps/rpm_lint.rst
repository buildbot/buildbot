.. bb:step:: RpmLint

.. _Step-RpmLint:

RpmLint
+++++++

The :bb:step:`RpmLint` step checks for common problems in RPM packages or spec files:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.RpmLint())

The step takes the following parameters

``fileloc``
    The file or directory to check.
    In case of a directory, it is recursively searched for RPMs and spec files to check.

``config``
    Path to a rpmlint config file.
    This is passed as the user configuration file if present.
