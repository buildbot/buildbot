ReporterBase
++++++++++++

.. py:currentmodule:: buildbot.reporters.base

.. py:class:: ReporterBase(generators)

    :class:`ReporterBase` is a base class used to implement various reporters.
    It accepts a list of :ref:`report generators<Report-Generators>` which define what messages to issue on what events.
    If generators decide that an event needs a report, then the ``sendMessage`` function is called.
    The ``sendMessage`` function should be implemented by deriving classes.

    :param generators:
        (a list of report generator instances)
        A list of report generators to manage.

    .. py:method:: sendMessage(self, reports)

        Sends the reports via the mechanism implemented by the specific implementation of the reporter.
        The reporter is expected to interpret all reports, figure out the best mechanism for reporting and report the given information.

        .. note::
            The API provided by the sendMessage function is not yet stable and is subject to change.

        :param reports:
            A list of dictionaries, one for each generator that provided a report.

Frequently used report keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
    The list of report keys and their meanings are currently subject to change.

This documents frequently used keys within the dictionaries that are passed to the ``sendMessage`` function.

 - ``body``: (string)
    The body of the report to be sent, usually sent as the body of e.g. email.

 - ``subject``: (string or ``None``)
    The subject of the report to be sent or ``None`` if nothing was supplied.

 - ``type``: (string)
    The type of the body of the report.
    The following are currently supported: ``plain`` and ``html``.

 - ``builder_name``:  (string)
    The name of the builder corresponding to the build or buildset that the report describes.

 - ``results``: (an instance of a result value from ``buildbot.process.results``)
    The current result of the build.

 - ``builds`` (a list of build dictionaries as reported by the data API)
    A list of builds that the report describes.

 - ``users`` (a list of strings)
    A list of users to send the report to.

 - ``patches`` (a list of patch dictionaries corresponding to sourcestamp's ``patch`` values)
    A list of patches applied to the build or buildset that is being built.

 - ``logs`` (a list of dictionaries corresponding to logs as reported by the data API)
    A list of logs produced by the build(s) so far.
    The following two keys are provided in addition to what the data API provides:

    - ``stepname`` (string) The name of the step that produced the log.

    - ``content`` (string) The content of the log.
