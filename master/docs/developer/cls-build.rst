Builds
======

.. py:module:: buildbot.process.build

The :py:class:`Build` class represents a running build, with associated steps.

Build
-----

.. py:class:: Build

    .. py:attribute:: buildid

        The ID of this build in the database.

    .. py:method:: getSummaryStatistic(name, summary_fn, initial_value=None)

        :param name: statistic name to summarize
        :param summary_fn: callable with two arguments that will combine two values
        :param initial_value: first value to pass to ``summary_fn``
        :returns: summarized result

        This method summarizes the named step statistic over all steps in which it exists, using ``combination_fn`` and ``initial_value`` to combine multiple results into a single result.
        This translates to a call to Python's ``reduce``::

            return reduce(summary_fn, step_stats_list, initial_value)

    .. py:method:: getUrl()

        :returns: Url as string

        Returns url of the build in the UI.
        Build must be started.
        This is useful for customs steps.
