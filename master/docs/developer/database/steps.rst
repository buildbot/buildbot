Steps connector
~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.steps

.. index:: double: Steps; DB Connector Component

.. py:class:: StepsConnectorComponent

    This class handles the steps performed within the context of a build.
    Within a build, each step has a unique name and a unique 0-based number.

    An instance of this class is available at ``master.db.steps``.

    .. index:: stepdict, stepid

    Builds are indexed by *stepid* and their contents are represented as *stepdicts* (step dictionaries), with the following keys:

    * ``id`` (the step ID, globally unique)
    * ``number`` (the step number, unique only within the build)
    * ``name`` (the step name, an 50-character :ref:`identifier <type-identifier>` unique only within the build)
    * ``buildid`` (the ID of the build containing this step)
    * ``started_at`` (datetime at which this step began)
    * ``complete_at`` (datetime at which this step finished, or None if it is ongoing)
    * ``state_string`` (short string describing the step's state)
    * ``results`` (results of this step; see :ref:`Build-Result-Codes`)
    * ``urls`` (list of URLs produced by this step. Each urls is stored as a dictionary with keys `name` and `url`)
    * ``hidden`` (true if the step should be hidden in status displays)

    .. py:method:: getStep(stepid=None, buildid=None, number=None, name=None)

        :param integer stepid: the step id to retrieve
        :param integer buildid: the build from which to get the step
        :param integer number: the step number
        :param name: the step name
        :type name: 50-character :ref:`identifier <type-identifier>`
        :returns: stepdict via Deferred

        Get a single step.
        The step can be specified by:

            * ``stepid`` alone
            * ``buildid`` and ``number``, the step number within that build
            * ``buildid`` and ``name``, the unique step name within that build

    .. py:method:: getSteps(buildid)

        :param integer buildid: the build from which to get the step
        :returns: list of stepdicts, sorted by number, via Deferred

        Get all steps in the given build, ordered by number.

    .. py:method:: addStep(self, buildid, name, state_string)

        :param integer buildid: the build to which to add the step
        :param name: the step name
        :type name: 50-character :ref:`identifier <type-identifier>`
        :param unicode state_string: the initial state of the step
        :returns: tuple of step ID, step number, and step name, via Deferred

        Add a new step to a build.
        The given name will be used if it is unique; otherwise, a unique numerical suffix will be appended.

    .. py:method:: setStepStateString(stepid, state_string):

        :param integer stepid: step ID
        :param unicode state_string: updated state of the step
        :returns: Deferred

        Update the state string for the given step.

    .. py:method:: finishStep(stepid, results, hidden)

        :param integer stepid: step ID
        :param integer results: step result
        :param bool hidden: true if the step should be hidden
        :returns: Deferred

        Mark the given step as finished, with ``complete_at`` set to the current time.

        .. note::

            This update is done unconditionally, even if the steps are already finished.

    .. py:method:: addURL(self, stepid, name, url)

        :param integer stepid: the stepid to add the url.
        :param string name: the url name
        :param string url: the actual url
        :returns: None via deferred

        Add a new url to a step.
        The new url is added to the list of urls.
