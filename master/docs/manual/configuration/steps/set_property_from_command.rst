.. bb:step:: SetPropertyFromCommand

.. _Step-SetPropertyFromCommand:

SetPropertyFromCommand
++++++++++++++++++++++

.. py:class:: buildbot.steps.shell.SetPropertyFromCommand

.. note::

    This step is being migrated to :ref:`new-style<New-Style-Build-Steps>`.
    A new-style equivalent is provided as ``SetPropertyFromCommand``.
    This should be inherited by any custom steps until :ref:`Buildbot 3.0 is released<3.0_Upgrading>`.
    Regular uses without inheritance are not affected.

This buildstep is similar to :bb:step:`ShellCommand`, except that it captures the output of the command into a property.
It is usually used like this:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.SetPropertyFromCommand(command="uname -a", property="uname"))

This runs ``uname -a`` and captures its stdout, stripped of leading and trailing whitespace, in the property ``uname``.
To avoid stripping, add ``strip=False``.

The ``property`` argument can be specified as an :ref:`Interpolate` object, allowing the property name to be built from other property values.

Passing ``includeStdout=False`` (defaults to ``True``) stops capture from stdout.

Passing ``includeStderr=True`` (defaults to ``False``) allows capture from stderr.

The more advanced usage allows you to specify a function to extract properties from the command output.
Here you can use regular expressions, string interpolation, or whatever you would like.
In this form, :func:`extract_fn` should be passed, and not :class:`Property`.
The :func:`extract_fn` function is called with three arguments: the exit status of the command, its standard output as a string, and its standard error as a string.
It should return a dictionary containing all new properties.

Note that passing in :func:`extract_fn` will set ``includeStderr`` to ``True``.

.. code-block:: python

    def glob2list(rc, stdout, stderr):
        jpgs = [l.strip() for l in stdout.split('\n')]
        return {'jpgs': jpgs}

    f.addStep(SetPropertyFromCommand(command="ls -1 *.jpg", extract_fn=glob2list))

Note that any ordering relationship of the contents of stdout and stderr is lost.
For example, given:

.. code-block:: python

    f.addStep(SetPropertyFromCommand(
        command="echo output1; echo error >&2; echo output2",
        extract_fn=my_extract))

Then ``my_extract`` will see ``stdout="output1\noutput2\n"`` and ``stderr="error\n"``.

Avoid using the ``extract_fn`` form of this step with commands that produce a great deal of output, as the output is buffered in memory until complete.
