.. index:: Buildstep Parameter

.. _Buildstep-Common-Parameters:

Parameters Common to all Steps
------------------------------

All :class:`BuildStep`\s accept some common parameters.
Some of these control how their individual status affects the overall build.
Others are used to specify which `Locks` (see :ref:`Interlocks`) should be acquired before allowing the step to run.

Arguments common to all :class:`BuildStep` subclasses:

``name``
    The name used to describe the step on the status display.
    Since 0.9.8, this argument might be renderable.

.. index:: Buildstep Parameter; haltOnFailure

``haltOnFailure``
    If ``True``, a ``FAILURE`` of this build step will cause the build to halt immediately.
    Any steps with ``alwaysRun=True`` will still be run.
    Generally speaking, ``haltOnFailure`` implies ``flunkOnFailure`` (the default for most :class:`BuildStep`\s).
    In some cases, particularly with a series of tests, it makes sense to ``haltOnFailure`` if something fails early on but not ``flunkOnFailure``.
    This can be achieved with ``haltOnFailure=True``, ``flunkOnFailure=False``.

.. index:: Buildstep Parameter; flunkOnWarnings

``flunkOnWarnings``
    When ``True``, a ``WARNINGS`` or ``FAILURE`` of this build step will mark the overall build as ``FAILURE``.
    The remaining steps will still be executed.

.. index:: Buildstep Parameter; flunkOnFailure

``flunkOnFailure``
    When ``True``, a ``FAILURE`` of this build step will mark the overall build as a ``FAILURE``.
    The remaining steps will still be executed.

.. index:: Buildstep Parameter; warnOnWarnings

``warnOnWarnings``
    When ``True``, a ``WARNINGS`` or ``FAILURE`` of this build step will mark the overall build as having ``WARNINGS``.
    The remaining steps will still be executed.

.. index:: Buildstep Parameter; warnOnFailure

``warnOnFailure``
    When ``True``, a ``FAILURE`` of this build step will mark the overall build as having ``WARNINGS``.
    The remaining steps will still be executed.

.. index:: Buildstep Parameter; alwaysRun

``alwaysRun``
    If ``True``, this build step will always be run, even if a previous buildstep with ``haltOnFailure=True`` has failed.

.. index:: Buildstep Parameter; description

``description``
    This will be used to describe the command (on the Waterfall display) while the command is still running.
    It should be a single imperfect-tense verb, like `compiling` or `testing`.
    The preferred form is a single, short string, but for historical reasons a list of strings is also acceptable.

.. index:: Buildstep Parameter; descriptionDone

``descriptionDone``
    This will be used to describe the command once it has finished.
    A simple noun like `compile` or `tests` should be used.
    Like ``description``, this may either be a string or a list of short strings.

    If neither ``description`` nor ``descriptionDone`` are set, the actual command arguments will be used to construct the description.
    This may be a bit too wide to fit comfortably on the Waterfall display.

    All subclasses of :py:class:`BuildStep` will contain the description attributes.
    Consequently, you could add a :bb:step:`ShellCommand` step like so:

    .. code-block:: python

        from buildbot.plugins import steps

        f.addStep(steps.ShellCommand(command=["make", "test"],
                                     description="testing",
                                     descriptionDone="tests"))

.. index:: Buildstep Parameter; descriptionSuffix

``descriptionSuffix``
    This is an optional suffix appended to the end of the description (ie, after ``description`` and ``descriptionDone``).
    This can be used to distinguish between build steps that would display the same descriptions in the waterfall.
    This parameter may be a string, a list of short strings or ``None``.

    For example, a builder might use the :bb:step:`Compile` step to build two different codebases.
    The ``descriptionSuffix`` could be set to `projectFoo` and `projectBar`, respectively for each step, which will result in the full descriptions `compiling projectFoo` and `compiling projectBar` to be shown in the waterfall.

.. index:: Buildstep Parameter; doStepIf

``doStepIf``
    A step can be configured to only run under certain conditions.
    To do this, set the step's ``doStepIf`` to a boolean value, or to a function that returns a boolean value or Deferred.
    If the value or function result is false, then the step will return ``SKIPPED`` without doing anything.
    Otherwise, the step will be executed normally.
    If you set ``doStepIf`` to a function, that function should accept one parameter, which will be the :class:`BuildStep` object itself.

.. index:: Buildstep Parameter; hideStepIf

``hideStepIf``
    A step can be optionally hidden from the waterfall and build details web pages.
    To do this, set the step's ``hideStepIf`` to a boolean value, or a function that takes two parameters (the results and the :class:`BuildStep`) and returns a boolean value.
    Steps are always shown while they execute; however, after the step has finished, this parameter is evaluated (if it's a function), and if the value is true, the step is hidden.
    For example, in order to hide the step if the step has been skipped:

    .. code-block:: python

        factory.addStep(Foo(..., hideStepIf=lambda results, s: results==SKIPPED))

.. index:: Buildstep Parameter; locks

``locks``
    A list of ``Locks`` (instances of :class:`buildbot.locks.WorkerLock` or :class:`buildbot.locks.MasterLock`) that should be acquired before starting this :py:class:`BuildStep`.
    Alternatively, this could be a renderable that returns this list during build execution.
    This lets you defer picking the locks to acquire until the build step is about to start running.
    The ``Locks`` will be released when the step is complete.
    Note that this is a list of actual :class:`Lock` instances, not names.
    Also note that all Locks must have unique names.
    See :ref:`Interlocks`.

.. index:: Buildstep Parameter; logEncoding

``logEncoding``
    The character encoding to use to decode logs produced during the execution of this step.
    This overrides the default :bb:cfg:`logEncoding`; see :ref:`Log-Encodings`.

.. index:: Buildstep Parameter; updateBuildSummaryPolicy

``updateBuildSummaryPolicy``
    The policy to use to propagate the step summary to the build summary.
    If False, the build summary will never include the step summary.
    If True, the build summary will always include the step summary.
    If set to a list (e.g. ``[FAILURE, EXCEPTION]``), the step summary will be propagated if the step results id is present in that list.
    If not set or None, the default is computed according to other BuildStep parameters using following algorithm:

    .. code-block:: python

        self.updateBuildSummaryPolicy = [EXCEPTION, RETRY, CANCELLED]
        if self.flunkOnFailure or self.haltOnFailure or self.warnOnFailure:
            self.updateBuildSummaryPolicy.append(FAILURE)
        if self.warnOnWarnings or self.flunkOnWarnings:
            self.updateBuildSummaryPolicy.append(WARNINGS)

    Note that in a custom step, if :py:meth:`BuildStep.getResultSummary` is overridden and sets the ``build`` summary, ``updateBuildSummaryPolicy`` is ignored and the ``build`` summary will be used regardless.
