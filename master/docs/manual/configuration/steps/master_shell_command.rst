.. bb:step:: MasterShellCommand

.. _Step-MasterShellCommand:

MasterShellCommand
++++++++++++++++++


.. py:class:: buildbot.steps.master.MasterShellCommand

Occasionally, it is useful to execute some task on the master, for example to create a directory, deploy a build result, or trigger some other centralized processing.
This is possible, in a limited fashion, with the :bb:step:`MasterShellCommand` step.

This step operates similarly to a regular :bb:step:`ShellCommand`, but executes on the master, instead of the worker.
To be clear, the enclosing :class:`Build` object must still have a worker object, just as for any other step -- only, in this step, the worker does not do anything.

In the following example, the step renames a tarball based on the day of the week.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.FileUpload(workersrc="widgetsoft.tar.gz",
                         masterdest="/var/buildoutputs/widgetsoft-new.tar.gz"))
    f.addStep(steps.MasterShellCommand(
        command="mv widgetsoft-new.tar.gz widgetsoft-`date +%a`.tar.gz",
        workdir="/var/buildoutputs"))

.. note::

   By default, this step passes a copy of the buildmaster's environment variables to the subprocess.
   To pass an explicit environment instead, add an ``env={..}`` argument.

Environment variables constructed using the ``env`` argument support expansion so that if you just want to prepend  :file:`/home/buildbot/bin` to the :envvar:`PATH` environment variable, you can do it by putting the value ``${PATH}`` at the end of the value like in the example below.
Variables that don't exist on the master will be replaced by ``""``.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.MasterShellCommand(
                  command=["make", "www"],
                  env={'PATH': ["/home/buildbot/bin",
                                "${PATH}"]}))

Note that environment values must be strings (or lists that are turned into strings).
In particular, numeric properties such as ``buildnumber`` must be substituted using :ref:`Interpolate`.

``workdir``
   (optional) The directory from which the command will be run.

``interruptSignal``
   (optional) Signal to use to end the process if the step is interrupted.
