Steps
=====

.. bb:rtype:: step

    :attr integer stepid: the unique ID of this step
    :attr integer number: the number of this step (sequential within the build)
    :attr name: the step name, unique within the build
    :type name: 50-character :ref:`identifier <type-identifier>`
    :attr integer buildid: id of the build containing this step
    :attr timestamp started_at: time at which this step started, or None if it hasn't started yet 
    :attr boolean complete: true if this step is complete
    :attr timestamp complete_at: time at which this step was complete, or None if it's still running
    :attr integer results: the results of the step (see :ref:`Build-Result-Codes`), or None if not complete
    :attr unicode state_string: a string giving detail on the state of the build.
        The first is usually one word or phrase; the remainder are sized for one-line display.
    :attr urls: a list of URLs associated with this step.
    :type urls: list of dictionaries with keys `name` and `url`
    :attr boolean hidden: true if the step should not be displayed

    This resource type describes a step in a build.
    Steps have unique IDs, but are most commonly accessed by name in the context of their containing builds.

    .. bb:rpath:: /step/:stepid

        :pathkey integer stepid: the ID of the step

        This path selects a specific step, identified by its step ID.

    .. bb:rpath:: /build/:buildid/step

        :pathkey integer buildid: the ID of the build

        This path lists steps for the given build, sorted by number.

    .. bb:rpath:: /build/:buildid/step/:step_name

        :pathkey integer buildid: the ID of the build
        :pathkey identifier step_name: the name of the step within the build

        This path selects a specific step, identified by its build ID and step name.

    .. bb:rpath:: /build/:buildid/step/:step_number

        :pathkey integer buildid: the ID of the build
        :pathkey integer step_number: the number of the step within the build

        This path selects a specific step, identified by its build ID and step number.

    .. bb:rpath:: /builder/:builderid/build/:build_number/step

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder

        This path lists steps for the given build, sorted by number.

    .. bb:rpath:: /builder/:builderid/build/:build_number/step/:name

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder
        :pathkey identifier name: the name of the step within the build

        This path selects a specific step, identified by its builder, build number, and step name.

    .. bb:rpath:: /builder/:builderid/build/:build_number/step/:step_number

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder
        :pathkey integer step_number: the number of the step within the build

        This path selects a specific step, identified by its builder, build number, and step number.

Update Methods
--------------

All update methods are available as attributes of ``master.data.updates``.

.. py:class:: buildbot.data.steps.StepResourceType

    .. py:method:: newStep(buildid, name)

        :param integer buildid: buildid containing this step
        :param name: name for the step
        :type name: 50-character :ref:`identifier <type-identifier>`
        :returns: (stepid, number, name) via Deferred

        Create a new step and return its ID, number, and name.
        Note that the name may be different from the requested name, if that name was already in use.
        The state strings for the new step will be set to 'pending'.

    .. py:method:: startStep(stepid)

        :param integer stepid: the step to modify

        Start the step.

    .. py:method:: setStepStateString(stepid, state_string)

        :param integer stepid: the step to modify
        :param unicode state_string: new state strings for this step

        Replace the existing state string for a step with a new list.

    .. py:method:: addStepURL(stepid, name, url):

        :param integer stepid: the step to modify
        :param string name: the url name
        :param string url: the actual url
        :returns: None via deferred

        Add a new url to a step.
        The new url is added to the list of urls.

    .. py:method:: finishStep(stepid, results, hidden)

        :param integer stepid: the step to modify
        :param integer results: the step's results
        :param boolean hidden: true if the step should not be displayed

        Mark the step as finished at the current time, with the given results.
