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

    Many message formatters support ``want_steps`` argument. If it is set, then build will contain
    ``steps`` key with a list of step dictionaries as reported by the data API.

    Many message formatters support ``want_logs`` argument. If it is set, then steps will contain
    ``logs`` key with a list of logs dictionaries as reported by the data API.

    The logs dictionaries contain the following keys in addition to what the data API provides:

    - ``stepname`` (string) The name of the step that produced the log.

    - ``url`` (string) The URL to the interactive page that displays the log contents

    - ``url_raw`` (string) The URL to the page that downloads the log contents as a file

    - ``url_raw_inline`` (string) The URL to the page that shows the log contents directly in the
        browser.

    - ``content`` (optional string) The content of the log. The content of the log is attached only
        if directed by ``want_logs_content`` argument of message formatters or ``add_logs``
        argument of report generators.

 - ``buildset`` (a buildset dictionary as reported by the data API)
    The buildset that is being described.

 - ``users`` (a list of strings)
    A list of users to send the report to.

 - ``patches`` (a list of patch dictionaries corresponding to sourcestamp's ``patch`` values)
    A list of patches applied to the build or buildset that is being built.

 - ``logs`` (a list of dictionaries corresponding to logs as reported by the data API)
    A list of logs produced by the build(s) so far.
    The log dictionaries have the same enhancements that are described in the ``build`` section
    above.

 - ``extra_info`` (a dictionary of dictionaries with string keys in both)
    A list of additional reporter-specific data to apply.
