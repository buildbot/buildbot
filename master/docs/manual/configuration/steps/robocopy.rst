.. bb:step:: Robocopy

.. _Step-Robocopy:

Robocopy
++++++++

.. py:class:: buildbot.steps.mswin.Robocopy

This step runs ``robocopy`` on Windows.

`Robocopy <https://technet.microsoft.com/en-us/library/cc733145.aspx>`_ is available in versions of Windows starting with Windows Vista and Windows Server 2008.
For previous versions of Windows, it's available as part of the `Windows Server 2003 Resource Kit Tools <https://www.microsoft.com/en-us/download/details.aspx?id=17657>`_.

.. code-block:: python

    from buildbot.plugins import steps, util

    f.addStep(
        steps.Robocopy(
            name='deploy_binaries',
            description='Deploying binaries...',
            descriptionDone='Deployed binaries.',
            source=util.Interpolate('Build\\Bin\\%(prop:configuration)s'),
            destination=util.Interpolate('%(prop:deploy_dir)\\Bin\\%(prop:configuration)s'),
            mirror=True
        )
    )

Available constructor arguments are:

``source``
    The path to the source directory (mandatory).

``destination``
    The path to the destination directory (mandatory).

``files``
    An array of file names or patterns to copy.

``recursive``
    Copy files and directories recursively (``/E`` parameter).

``mirror``
    Mirror the source directory in the destination directory, including removing files that don't exist anymore (``/MIR`` parameter).

``move``
    Delete the source directory after the copy is complete (``/MOVE`` parameter).

``exclude_files``
    An array of file names or patterns to exclude from the copy (``/XF`` parameter).

``exclude_dirs``
    An array of directory names or patterns to exclude from the copy (``/XD`` parameter).

``custom_opts``
    An array of custom parameters to pass directly to the ``robocopy`` command.

``verbose``
    Whether to output verbose information (``/V /TS /FP`` parameters).

Note that parameters ``/TEE /NP`` will always be appended to the command to signify, respectively, to output logging to the console, use Unicode logging, and not print any percentage progress information for each file.
