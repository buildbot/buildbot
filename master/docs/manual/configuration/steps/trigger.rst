.. index:: Properties; triggering schedulers

.. bb:step:: Trigger

.. _Step-Trigger:

Trigger
-------

.. py:class:: buildbot.steps.trigger.Trigger

The counterpart to the :bb:Sched:`Triggerable` scheduler is the :bb:step:`Trigger` build step:

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Trigger(schedulerNames=['build-prep'],
                            waitForFinish=True,
                            updateSourceStamp=True,
                            set_properties={ 'quick' : False }))

The SourceStamps to use for the triggered build are controlled by the arguments ``updateSourceStamp``, ``alwaysUseLatest``, and ``sourceStamps``.

Hyperlinks are added to the build detail web pages for each triggered build.

``schedulerNames``
    Lists the :bb:sched:`Triggerable` schedulers that should be triggered when this step is executed.

    .. note::

        It is possible, but not advisable, to create a cycle where a build continually triggers itself, because the schedulers are specified by name.

``unimportantSchedulerNames``
    When ``waitForFinish`` is ``True``, all schedulers in this list will not cause the trigger step to fail. unimportantSchedulerNames must be a subset of schedulerNames.
    If ``waitForFinish`` is ``False``, unimportantSchedulerNames will simply be ignored.

``waitForFinish``
    If ``True``, the step will not finish until all of the builds from the triggered schedulers have finished.

    If ``False`` (the default) or not given, then the buildstep succeeds immediately after triggering the schedulers.

``updateSourceStamp``
    If ``True`` (the default), then the step updates the source stamps given to the :bb:sched:`Triggerable` schedulers to include ``got_revision`` (the revision actually used in this build) as ``revision`` (the revision to use in the triggered builds).
    This is useful to ensure that all of the builds use exactly the same source stamps, even if other :class:`Change`\s have occurred while the build was running.

    If ``False`` (and neither of the other arguments are specified), then the exact same SourceStamps are used.

``alwaysUseLatest``
    If ``True``, then no SourceStamps are given, corresponding to using the latest revisions of the repositories specified in the Source steps.
    This is useful if the triggered builds use to a different source repository.

``sourceStamps``
    Accepts a list of dictionaries containing the keys ``branch``, ``revision``, ``repository``, ``project``, and optionally ``patch_level``, ``patch_body``, ``patch_subdir``, ``patch_author`` and ``patch_comment`` and creates the corresponding SourceStamps.
    If only one sourceStamp has to be specified then the argument ``sourceStamp`` can be used for a dictionary containing the keys mentioned above.
    The arguments ``updateSourceStamp``, ``alwaysUseLatest``, and ``sourceStamp`` can be specified using properties.

``set_properties``
    Allows control of the properties that are passed to the triggered scheduler.
    The parameter takes a dictionary mapping property names to values.
    You may use :ref:`Interpolate` here to dynamically construct new property values.
    For the simple case of copying a property, this might look like:

    .. code-block:: python

        set_properties={"my_prop1" : Property("my_prop1"),
                        "my_prop2" : Property("my_prop2")}

    where ``Property`` is an instance of ``buildbot.process.properties.Property``.

    .. note::

        The ``copy_properties`` parameter, given a list of properties to copy into the new build request, has been deprecated in favor of explicit use of ``set_properties``.

.. _Dynamic-Trigger:

Dynamic Trigger
+++++++++++++++

Sometimes it is desirable to select which scheduler to trigger, and which properties to set dynamically, at the time of the build.
For this purpose, the Trigger step supports a method that you can customize in order to override statically defined ``schedulernames``, ``set_properties`` and optionally ``unimportant``.

.. py:method:: getSchedulersAndProperties()

    :returns: list of dictionaries containing the keys 'sched_name', 'props_to_set' and 'unimportant' optionally via deferred.

    This method returns a list of dictionaries describing what scheduler to trigger, with which properties and if the scheduler is unimportant.
    Old style list of tuples is still supported, in which case unimportant is considered ``False``.
    The properties should already be rendered (ie, concrete value, not objects wrapped by ``Interpolate`` or
    ``Property``). Since this function happens at build-time, the property values are available from the
    step and can be used to decide what schedulers or properties to use.

    With this method, you can also trigger the same scheduler multiple times with different set of properties.
    The sourcestamp configuration is however the same for each triggered build request.

