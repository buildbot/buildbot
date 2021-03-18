.. _Worker-Filesystem-Steps:

Worker Filesystem Steps
-----------------------

Here are some buildsteps for manipulating the worker's filesystem.

.. bb:step:: FileExists

FileExists
++++++++++

This step will assert that a given file exists, failing if it does not.
The filename can be specified with a property.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.FileExists(file='test_data'))

This step requires worker version 0.8.4 or later.

.. bb:step:: CopyDirectory

CopyDirectory
+++++++++++++

This command copies a directory on the worker.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.CopyDirectory(src="build/data", dest="tmp/data"))

This step requires worker version 0.8.5 or later.

The CopyDirectory step takes the following arguments:

``timeout``
    If the copy command fails to produce any output for this many seconds, it is assumed to be locked up and will be killed.
    This defaults to 120 seconds.
    Pass ``None`` to disable.

``maxTime``
    If the command takes longer than this many seconds, it will be killed.
    This is disabled by default.

.. bb:step:: RemoveDirectory

RemoveDirectory
+++++++++++++++

This command recursively deletes a directory on the worker.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.RemoveDirectory(dir="build/build"))

This step requires worker version 0.8.4 or later.

.. bb:step:: MakeDirectory

MakeDirectory
+++++++++++++

This command creates a directory on the worker.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.MakeDirectory(dir="build/build"))

This step requires worker version 0.8.5 or later.
