BuildFactory
============

BuildFactory Implementation Note
--------------------------------

The default :class:`BuildFactory`, provided in the :mod:`buildbot.process.factory` module, contains an internal list of `BuildStep specifications`: a list of ``(step_class, kwargs)`` tuples for each.
These specification tuples are constructed when the config file is read, by asking the instances passed to :meth:`addStep` for their subclass and arguments.

To support config files from Buildbot version 0.7.5 and earlier, :meth:`addStep` also accepts the ``f.addStep(shell.Compile, command=["make","build"])`` form, although its use is discouraged because then the ``Compile`` step doesn't get to validate or complain about its arguments until build time.
The modern pass-by-instance approach allows this validation to occur while the config file is being loaded, where the admin has a better chance of noticing problems.

When asked to create a :class:`Build`, the :class:`BuildFactory` puts a copy of the list of step specifications into the new :class:`Build` object.
When the :class:`Build` is actually started, these step specifications are used to create the actual set of :class:`BuildStep`\s, which are then executed one at a time.
This serves to give each Build an independent copy of each step.

Each step can affect the build process in the following ways:

* If the step's :attr:`haltOnFailure` attribute is ``True``, then a failure in the step (i.e. if it completes with a result of ``FAILURE``) will cause the whole build to be terminated immediately: no further steps will be executed, with the exception of steps with :attr:`alwaysRun` set to ``True``.
  :attr:`haltOnFailure` is useful for setup steps upon which the rest of the build depends: if the CVS checkout or :command:`./configure` process fails, there is no point in trying to compile or test the resulting tree.

* If the step's :attr:`alwaysRun` attribute is ``True``, then it will always be run, regardless of if previous steps have failed.
  This is useful for cleanup steps that should always be run to return the build directory or worker into a good state.

* If the :attr:`flunkOnFailure` or :attr:`flunkOnWarnings` flag is set, then a result of ``FAILURE`` or ``WARNINGS`` will mark the build as a whole as ``FAILED``.
  However, the remaining steps will still be executed.
  This is appropriate for things like multiple testing steps: a failure in any one of them will indicate that the build has failed, however it is still useful to run them all to completion.

* Similarly, if the :attr:`warnOnFailure` or :attr:`warnOnWarnings` flag is set, then a result of ``FAILURE`` or ``WARNINGS`` will mark the build as having ``WARNINGS``, and the remaining steps will still be executed.
  This may be appropriate for certain kinds of optional build or test steps.
  For example, a failure experienced while building documentation files should be made visible with a ``WARNINGS`` result but not be serious enough to warrant marking the whole build with a ``FAILURE``.

In addition, each :class:`Step` produces its own results, may create logfiles, etc.
However only the flags described above have any effect on the build as a whole.

The pre-defined :class:`BuildStep`\s like :class:`CVS` and :class:`Compile` have reasonably appropriate flags set on them already.
For example, without a source tree there is no point in continuing the build, so the :class:`CVS` class has the :attr:`haltOnFailure` flag set to ``True``.
Look in :file:`buildbot/steps/*.py` to see how the other :class:`Step`\s are marked.

Each :class:`Step` is created with an additional ``workdir`` argument that indicates where its actions should take place.
This is specified as a subdirectory of the worker's base directory, with a default value of :file:`build`.
This is only implemented as a step argument (as opposed to simply being a part of the base directory) because the CVS/SVN steps need to perform their checkouts from the parent directory.
