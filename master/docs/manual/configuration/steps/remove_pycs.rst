.. bb:step:: RemovePYCs

.. _Step-RemovePYCs:

RemovePYCs
++++++++++

.. py:class:: buildbot.steps.python_twisted.RemovePYCs

This is a simple built-in step that will remove ``.pyc`` files from the workdir.
This is useful in builds that update their source (and thus do not automatically delete ``.pyc`` files) but where some part of the build process is dynamically searching for Python modules.
Notably, trial has a bad habit of finding old test modules.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.RemovePYCs())
