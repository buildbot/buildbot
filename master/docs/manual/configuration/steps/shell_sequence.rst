.. bb:step:: ShellSequence

.. _Step-ShellSequence:

Shell Sequence
++++++++++++++

Some steps have a specific purpose, but require multiple shell commands to implement them.
For example, a build is often ``configure; make; make install``.
We have two ways to handle that:

* Create one shell command with all these.
  To put the logs of each commands in separate logfiles, we need to re-write the script as ``configure 1> configure_log; ...`` and to add these ``configure_log`` files as ``logfiles`` argument of the buildstep.
  This has the drawback of complicating the shell script, and making it harder to maintain as the logfile name is put in different places.

* Create three :bb:step:`ShellCommand` instances, but this loads the build UI unnecessarily.

:bb:step:`ShellSequence` is a class that executes not one but a sequence of shell commands during a build.
It takes as argument a renderable, or list of commands which are :class:`~buildbot.steps.shellsequence.ShellArg` objects.
Each such object represents a shell invocation.

The single :bb:step:`ShellSequence` argument aside from the common parameters is:

``commands``
    A list of :class:`~buildbot.steps.shellsequence.ShellArg` objects or a renderable that returns a list of :class:`~buildbot.steps.shellsequence.ShellArg` objects.

.. code-block:: python

    from buildbot.plugins import steps, util

    f.addStep(steps.ShellSequence(
        commands=[
            util.ShellArg(command=['configure']),
            util.ShellArg(command=['make'], logname='make'),
            util.ShellArg(command=['make', 'check_warning'], logname='warning',
                          warnOnFailure=True),
            util.ShellArg(command=['make', 'install'], logname='make install')
        ]))

All these commands share the same configuration of ``environment``, ``workdir`` and ``pty`` usage that can be set up the same way as in :bb:step:`ShellCommand`.

.. py:class:: buildbot.steps.shellsequence.ShellArg(self, command=None, logname=None, haltOnFailure=False, flunkOnWarnings=False, flunkOnFailure=False, warnOnWarnings=False, warnOnFailure=False)

    :param command: (see the :bb:step:`ShellCommand` ``command`` argument),
    :param logname: optional log name, used as the stdio log of the command

    The ``haltOnFailure``, ``flunkOnWarnings``, ``flunkOnFailure``, ``warnOnWarnings``, ``warnOnFailure`` parameters drive the execution of the sequence, the same way steps are scheduled in the build.
    They have the same default values as for buildsteps - see :ref:`Buildstep-Common-Parameters`.

    Any of the arguments to this class can be renderable.

    Note that if ``logname`` name does not start with the prefix ``stdio``, that prefix will be set like ``stdio <logname>``.
    If no ``logname`` is supplied, the output of the command will not be collected.


The two :bb:step:`ShellSequence` methods below tune the behavior of how the list of shell commands are executed, and can be overridden in subclasses.

.. py:class:: buildbot.steps.shellsequence.ShellSequence

    .. py:method:: shouldRunTheCommand(oneCmd)

        :param oneCmd: a string or a list of strings, as rendered from a :py:class:`~buildbot.steps.shellsequence.ShellArg` instance's ``command`` argument.

        Determine whether the command ``oneCmd`` should be executed.
        If ``shouldRunTheCommand`` returns ``False``, the result of the command will be recorded as SKIPPED.
        The default method skips all empty strings and empty lists.

    .. py:method:: getFinalState()

        Return the status text of the step in the end.
        The default value is to set the text describing the execution of the last shell command.

    .. py:method:: runShellSequence(commands):

        :param commands: list of shell args

        This method actually runs the shell sequence.
        The default ``run`` method calls ``runShellSequence``, but subclasses can override ``run`` to perform other operations, if desired.
